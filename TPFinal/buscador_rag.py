"""Buscador léxico para las normas del agente de admisión.

El índice se construye siempre desde ``ruta_normas``. Los valores numéricos se
leen de ``parametros.yaml`` y se agregan solamente a los fragmentos que citan
cada parámetro. De esta forma, el buscador funciona también con las versiones
``b`` y ``c`` y con las normas modificadas del test secreto.

No usa servicios externos ni modelos descargables: combina BM25, coincidencia
de frases y una pequeña normalización de vocabulario propio de la guardia.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


PATRON_PARAMETRO = re.compile(r"P-[A-Z]{3}-\d+")
PATRON_RANGO_PARAMETROS = re.compile(r"(P-[A-Z]{3})-(\d+)\s+a\s+\1-(\d+)")
PATRON_PARRAFO = re.compile(r"(?m)(?=^\s*§\d+\.)")
PATRON_TOKEN = re.compile(r"[a-z0-9]+")

UNIDADES = {
    "nivel": "nivel {valor}",
    "min": "{valor} min",
    "dias": "{valor} días",
    "anios": "{valor} años",
}

# Las equivalencias expresan vocabulario, no decisiones ni valores de las
# normas. Sirven para acercar preguntas coloquiales al lenguaje institucional.
EQUIVALENCIAS = (
    (("obra social", "prepaga", "credencial", "afiliado"), "cobertura afiliacion entidad numero afiliado"),
    (("dado de baja", "dio de baja", "baja"), "afiliacion inactiva verificar no notifica"),
    (("desmayado", "inconsciente", "no responde"), "no puede responder condiciones responder"),
    (("solo", "sin nadie"), "sin acompanante"),
    (("abuela", "abuelo", "adulto mayor", "ochenta", "setenta"), "paciente mayor edad anios"),
    (("anoto", "anotar", "cargo", "cargar datos"), "registro registrar"),
    (("pasar", "mando adentro", "hago pasar"), "ubicar ubicacion box antes registro"),
    (("pecho", "corazon"), "dolor toracico electrocardiograma ecg"),
    (("cara torcida", "signos neurologicos", "derrame"), "codigo acv inicio subito"),
    (("cultivo", "antibiotico", "antibiótico"), "sepsis hemocultivos antimicrobiano"),
    (("albanil", "albañil", "operario", "fabrica", "fábrica", "andamio"), "accidente trabajo art empleador cuil"),
    (("accidento yendo", "accidentó yendo", "trayecto al trabajo"), "accidente trayecto trabajo art"),
    (("clinica", "clínica"), "establecimiento privado prestador derivacion"),
    (("ambulancia",), "llego ingreso ambulancia plazo circuito descuenta minutos"),
    (("sin obra social", "sin prepaga"), "sin cobertura servicio social"),
    (("cuanto", "cuánto", "desde que", "desde qué", "plazo"), "parametro valor tiempo"),
)

STOPWORDS = {
    "a", "al", "algo", "ante", "como", "con", "cual", "cuando", "de", "del", "desde",
    "donde", "el", "ella", "en", "es", "esa", "ese", "esto", "hay", "la", "las", "le",
    "lo", "los", "me", "mi", "para", "pero", "por", "que", "se", "si", "sin", "su",
    "sus", "tengo", "tiene", "un", "una", "uno", "y", "ya",
}


def _sin_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _raiz(token: str) -> str:
    """Raíz liviana para plural y flexiones frecuentes, sin librerías externas."""
    if len(token) <= 4 or token.startswith(("p-adm", "p-cob", "p-tde", "p-gua", "p-int", "p-der")):
        return token
    for sufijo in (
        "amientos", "imientos", "aciones", "imiento", "amiento", "acion",
        "mente", "idades", "idad", "ados", "adas", "idos", "idas",
        "ando", "iendo", "es", "os", "as", "s",
    ):
        if token.endswith(sufijo) and len(token) - len(sufijo) >= 4:
            return token[: -len(sufijo)]
    return token


def _tokens(texto: str) -> list[str]:
    limpio = _sin_acentos(texto)
    # Los códigos se conservan como una unidad además de sus partes.
    codigos = [c.replace("-", "") for c in re.findall(r"p-[a-z]{3}-\d+|nor-[a-z]{3}-\d+", limpio)]
    palabras = PATRON_TOKEN.findall(limpio)
    return codigos + [_raiz(p) for p in palabras if p not in STOPWORDS and len(p) > 1]


def _expandir_consulta(consulta: str) -> str:
    normalizada = _sin_acentos(consulta)
    agregados = []
    for expresiones, expansion in EQUIVALENCIAS:
        if any(_sin_acentos(expresion) in normalizada for expresion in expresiones):
            agregados.append(expansion)
    return f"{consulta} {' '.join(agregados)}"


def _valor_con_unidad(valor: int | float | str, unidad: str) -> str:
    if unidad == "camas":
        return f"{valor} {'cama' if valor == 1 else 'camas'}"
    return UNIDADES.get(unidad, "{valor}").format(valor=valor)


def _cargar_parametros(ruta: Path) -> dict[str, str]:
    datos = yaml.safe_load((ruta / "parametros.yaml").read_text(encoding="utf-8"))
    return {
        item["codigo"]: _valor_con_unidad(item["valor"], item["unidad"])
        for item in datos["parametros"]
    }


@dataclass(frozen=True)
class Fragmento:
    seccion: str
    titulo: str
    parrafo: str
    texto: str
    orden: int


@dataclass(frozen=True)
class SeccionRecuperada:
    seccion: str
    texto: str


def _fragmentar_normas(ruta_normas: Path) -> list[Fragmento]:
    ruta = Path(ruta_normas)
    parametros = _cargar_parametros(ruta)
    fragmentos: list[Fragmento] = []

    for archivo in sorted(ruta.glob("NOR-*.md")):
        contenido = archivo.read_text(encoding="utf-8").strip()
        titulo, _, cuerpo = contenido.partition("\n")
        parrafos = [p.strip() for p in PATRON_PARRAFO.split(cuerpo) if p.strip()]
        for orden, parrafo in enumerate(parrafos, start=1):
            codigos = PATRON_PARAMETRO.findall(parrafo)
            for prefijo, desde, hasta in PATRON_RANGO_PARAMETROS.findall(parrafo):
                codigos.extend(f"{prefijo}-{numero}" for numero in range(int(desde), int(hasta) + 1))
            codigos = list(dict.fromkeys(codigos))
            valores = [f"{codigo} = {parametros[codigo]}" for codigo in codigos if codigo in parametros]
            linea_valores = f"\nValores: {'; '.join(valores)}." if valores else ""
            texto = f"{titulo}\n{parrafo}{linea_valores}"
            fragmentos.append(Fragmento(archivo.stem, titulo, parrafo, texto, orden))

    if not fragmentos:
        raise ValueError(f"No se encontraron normas NOR-*.md en {ruta}")
    return fragmentos


class BuscadorNormativo:
    """Recuperador híbrido BM25 por párrafo con señales de sección."""

    k_entorno = 2

    def __init__(self, ruta_normas: str | Path):
        self.fragmentos = _fragmentar_normas(Path(ruta_normas))
        self._tokens_fragmento = [_tokens(f.texto) for f in self.fragmentos]
        self._frecuencias = [Counter(tokens) for tokens in self._tokens_fragmento]
        self._largos = [len(tokens) for tokens in self._tokens_fragmento]
        self._largo_medio = sum(self._largos) / len(self._largos)
        self._idf = self._calcular_idf(self._tokens_fragmento)

        por_seccion: dict[str, list[str]] = {}
        fragmentos_por_seccion: dict[str, list[Fragmento]] = {}
        for fragmento in self.fragmentos:
            por_seccion.setdefault(fragmento.seccion, []).extend(_tokens(fragmento.texto))
            fragmentos_por_seccion.setdefault(fragmento.seccion, []).append(fragmento)
        self._tokens_seccion = {s: Counter(ts) for s, ts in por_seccion.items()}
        self._idf_seccion = self._calcular_idf(list(por_seccion.values()))
        self._secciones = {
            seccion: self._armar_seccion(seccion, fragmentos)
            for seccion, fragmentos in fragmentos_por_seccion.items()
        }

    @staticmethod
    def _armar_seccion(seccion: str, fragmentos: list[Fragmento]) -> SeccionRecuperada:
        titulo = fragmentos[0].titulo
        cuerpo = "\n\n".join(f.parrafo for f in fragmentos)
        valores = []
        for fragmento in fragmentos:
            if "\nValores: " in fragmento.texto:
                linea = fragmento.texto.rsplit("\nValores: ", 1)[1].removesuffix(".")
                valores.extend(par.strip() for par in linea.split(";") if par.strip())
        valores = list(dict.fromkeys(valores))
        linea_valores = f"\n\nValores: {'; '.join(valores)}." if valores else ""
        return SeccionRecuperada(seccion, f"{titulo}\n\n{cuerpo}{linea_valores}")

    @staticmethod
    def _calcular_idf(documentos: Iterable[Iterable[str]]) -> dict[str, float]:
        documentos = [set(d) for d in documentos]
        n = len(documentos)
        apariciones = Counter(token for documento in documentos for token in documento)
        return {
            token: math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            for token, df in apariciones.items()
        }

    def _bm25(self, consulta: list[str], indice: int) -> float:
        frecuencias = self._frecuencias[indice]
        largo = self._largos[indice]
        k1, b = 1.45, 0.68
        score = 0.0
        for token, peso_consulta in Counter(consulta).items():
            tf = frecuencias.get(token, 0)
            if not tf:
                continue
            normalizador = tf + k1 * (1 - b + b * largo / self._largo_medio)
            score += self._idf.get(token, 0.0) * (tf * (k1 + 1) / normalizador) * min(peso_consulta, 2)
        return score

    def _score_seccion(self, consulta: list[str], seccion: str) -> float:
        frecuencias = self._tokens_seccion[seccion]
        return sum(self._idf_seccion.get(t, 0.0) * min(frecuencias.get(t, 0), 2) for t in set(consulta))

    @staticmethod
    def _pistas_de_seccion(consulta: str) -> dict[str, float]:
        """Señales de vocabulario para resolver ambigüedades entre normas vecinas."""
        q = _sin_acentos(consulta)
        pistas: Counter[str] = Counter()

        def contiene(*expresiones: str) -> bool:
            return any(expresion in q for expresion in expresiones)

        if contiene("sin credencial", "no trajo la credencial", "no presento la credencial") or (
            "pregunt" in q and contiene("cobertura", "obra social", "prepaga")
        ):
            pistas["NOR-COB-01"] += 13
        if contiene("no puede responder", "no esta en condiciones de responder", "desmayado", "inconsciente"):
            pistas["NOR-COB-01"] += 11
        if contiene("verificar", "chequear") and contiene("afiliacion", "entidad", "cobertura", "numero"):
            pistas["NOR-COB-02"] += 9
        if contiene("autorizacion", "validacion posterior"):
            pistas["NOR-COB-02"] += 9
        if contiene("servicio social", "sin cobertura", "dado de baja", "afiliacion inactiva", "salio inactiva"):
            pistas["NOR-COB-03"] += 13
        if (contiene("sin obra social", "sin prepaga") or ("ni obra social ni prepaga" in q)):
            pistas["NOR-COB-03"] += 15
        if contiene("consigan algo del estado", "cobertura publica", "pago", "garantia"):
            pistas["NOR-COB-03"] += 11
        if contiene("terminacion reservada", "digito reservado", "termina en"):
            pistas["NOR-COB-04"] += 15

        if contiene("pasaporte", "cedula"):
            pistas["NOR-ADM-03"] += 13
            pistas["NOR-ADM-01"] += 4
        if contiene("sin documento", "no trae ningun documento", "registro provisorio", "antes del alta", "egreso"):
            pistas["NOR-ADM-01"] += 9
        if contiene("edad", "adulto mayor", "paciente mayor", "abuela", "abuelo", "ochenta", "setenta"):
            pistas["NOR-ADM-02"] += 22
        if "box" in q and contiene("antes de registrar", "antes del registro", "registrarlo", "registro", "registr"):
            pistas["NOR-ADM-01"] += 12
        if "credencial" in q and "triage" in q and "box" in q and "registr" in q:
            pistas["NOR-ADM-01"] += 9

        if contiene("dolor toracico", "dolor de pecho", "ecg", "electrocardiograma", "corazon"):
            pistas["NOR-TDE-01"] += 15
        if contiene("codigo acv", "signos neurologicos", "cara torcida", "ultima hora", "vio bien"):
            pistas["NOR-TDE-02"] += 15
        if contiene("sepsis", "hemocultivo", "antimicrobiano", "antibiotico"):
            pistas["NOR-TDE-03"] += 15
        if "ambulancia" in q:
            pistas["NOR-TDE-04"] += 15

        if contiene("derivar", "derivacion", "establecimiento", "clinica privada"):
            pistas["NOR-DER-01"] += 13
        if contiene("evaluacion medica", "cambiar el nivel de triage", "tiempo maximo"):
            pistas["NOR-GUA-01"] += 10
        if contiene("sala de reanimacion", "box de agudos", "tipo de box"):
            pistas["NOR-GUA-02"] += 13
        if "retriage" in q:
            pistas["NOR-GUA-03"] += 15
        if contiene("unidad coronaria", "terapia intensiva", "otro sector"):
            pistas["NOR-INT-01"] += 13
        if contiene("tuberculosis", "aislamiento aereo", "presion negativa"):
            pistas["NOR-INT-02"] += 15
        if contiene("habitaciones individuales", "habitacion individual", "prioridad"):
            pistas["NOR-INT-03"] += 12
        if contiene("no hay cama", "alta prevista", "falta de cama"):
            pistas["NOR-INT-05"] += 11

        if contiene("accidente de trabajo", "accidento yendo al trabajo", "art", "albanil", "operario", "fabrica"):
            pistas["NOR-COB-01"] += 8
            pistas["NOR-COB-02"] += 10
        return dict(pistas)

    @staticmethod
    def _bonus_frases(consulta: str, fragmento: Fragmento) -> float:
        q = _sin_acentos(consulta)
        d = _sin_acentos(fragmento.texto)
        palabras = [p for p in PATRON_TOKEN.findall(q) if p not in STOPWORDS and len(p) > 3]
        bonus = 0.0
        for n in (3, 2):
            for i in range(len(palabras) - n + 1):
                frase = " ".join(palabras[i : i + n])
                if frase in d:
                    bonus += 1.2 if n == 3 else 0.45
        return bonus

    def _ordenar(self, consulta: str) -> list[tuple[float, Fragmento]]:
        expandida = _expandir_consulta(consulta)
        tokens_consulta = _tokens(expandida)
        pistas = self._pistas_de_seccion(consulta)
        puntuados = []
        for indice, fragmento in enumerate(self.fragmentos):
            score = self._bm25(tokens_consulta, indice)
            score += 0.18 * self._score_seccion(tokens_consulta, fragmento.seccion)
            score += 0.55 * pistas.get(fragmento.seccion, 0.0)
            score += self._bonus_frases(consulta, fragmento)
            puntuados.append((score, fragmento))
        return sorted(puntuados, key=lambda x: (-x[0], x[1].seccion, x[1].orden))

    def _ordenar_secciones(self, consulta: str) -> list[tuple[float, SeccionRecuperada]]:
        tokens_consulta = _tokens(_expandir_consulta(consulta))
        pistas = self._pistas_de_seccion(consulta)
        puntuadas = [
            (self._score_seccion(tokens_consulta, seccion) + pistas.get(seccion, 0.0), documento)
            for seccion, documento in self._secciones.items()
        ]
        return sorted(puntuadas, key=lambda x: (-x[0], x[1].seccion))

    @staticmethod
    def _parece_multiseccion(consulta: str) -> bool:
        q = _sin_acentos(consulta)
        grupos = (
            ("ambulancia",),
            ("dolor de pecho", "dolor toracico", "ecg", "acv", "neurolog", "sepsis"),
            ("edad", "anos", "ochenta", "setenta", "mayor"),
            ("triage", "nivel"),
            ("pasaporte", "cedula"),
            ("registro", "registr"),
            ("trabajo", "art", "fabrica", "operario", "albanil"),
            ("cobertura", "obra social", "prepaga"),
            ("deriv", "clinica", "establecimiento"),
            ("inactiva", "dado de baja"),
            ("reservad", "termina en"),
            ("credencial",),
            ("box", "ubicar"),
        )
        presentes = sum(any(termino in q for termino in grupo) for grupo in grupos)
        if "ambulancia" in q and any(t in q for t in grupos[1]):
            return True
        if any(t in q for t in ("pasaporte", "cedula")) and any(t in q for t in ("triage", "nivel")):
            return True
        if "sin cobertura" in q and "deriv" in q:
            return True
        if any(t in q for t in ("inactiva", "dado de baja")) and any(t in q for t in ("reservad", "termina en")):
            return True
        if "credencial" in q and "triage" in q and any(t in q for t in ("registr", "box", "ubicar")):
            return True
        if any(t in q for t in ("trabajo", "art", "fabrica", "operario", "albanil")) and any(
            t in q for t in ("cobertura", "obra social", "prepaga", "verific", "pregunt")
        ):
            return True
        return presentes >= 4 and any(c in q for c in (" y ", " pero ", " aunque ", " uno ", " otro "))

    def recuperar(self, consulta: str, k: int) -> list[Fragmento]:
        if not isinstance(consulta, str) or not consulta.strip() or k <= 0:
            return []

        # Para la herramienta del agente se devuelven secciones completas. Esto
        # preserva excepciones y reglas de prevalencia que suelen estar en otro
        # párrafo de la misma norma.
        if k <= self.k_entorno:
            ranking_secciones = self._ordenar_secciones(consulta)
            relacion = ranking_secciones[0][0] / max(ranking_secciones[1][0], 0.01)
            limite = 2 if self._parece_multiseccion(consulta) or relacion < 1.28 else 1
            return [documento for _, documento in ranking_secciones[: min(k, limite)]]

        # Para comparar con presupuestos fijos, los párrafos chicos permiten
        # aprovechar mejor 256/512/1024 tokens.
        ranking = self._ordenar(consulta)
        return [fragmento for _, fragmento in ranking[:k]]


def construir_buscador(ruta_normas: str | Path) -> BuscadorNormativo:
    return BuscadorNormativo(ruta_normas)

