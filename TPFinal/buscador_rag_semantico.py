"""RAG léxico-semántico sin enrutamiento manual hacia documentos.

La expansión se realiza mediante conceptos generales y bidireccionales. El
mismo normalizador se aplica a consultas y normas: ninguna frase suma puntos a
un código ``NOR-*`` concreto. El ranking combina BM25 por campos, n-gramas de
caracteres, títulos, cobertura conceptual, apartados, segmentación de consultas
y referencias explícitas presentes en el propio corpus.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from buscador_rag import Fragmento, SeccionRecuperada, _fragmentar_normas, _sin_acentos, _tokens
from buscador_rag_general import _BM25, _IndiceCaracteres, _normalizar_puntajes


# Diccionario de lenguaje del dominio. Solo produce conceptos; deliberadamente
# no contiene nombres de archivos ni pesos dirigidos a documentos.
CONCEPTOS: dict[str, tuple[str, ...]] = {
    "identidad": ("documento", "dni", "cedula", "pasaporte", "identificacion", "identidad"),
    "registro": ("registro", "registrar", "inscripcion", "ficha", "cargar datos", "alta en el sistema"),
    "provisorio": ("provisorio", "provisoria", "temporal", "transitorio", "provisional"),
    "definitivo": ("definitivo", "definitiva", "permanente", "confirmado"),
    "egreso": ("egreso", "alta", "abandona la guardia", "se va de la guardia"),
    "paciente_mayor": ("adulto mayor", "persona mayor", "paciente mayor", "anciano", "anciana", "abuelo", "abuela"),
    "triage": ("triage", "categoria de gravedad", "clasificacion de gravedad", "nivel de urgencia", "prioridad clinica"),
    "ubicacion": ("ubicar", "ubicacion", "hacer pasar", "ingresar", "mandar adentro", "asignar lugar"),
    "box": ("box", "consultorio de guardia", "reanimacion", "area de agudos", "espacio asistencial"),
    "cobertura": ("cobertura", "seguro medico", "plan medico", "obra social", "prepaga", "mutual", "aseguradora"),
    "credencial": ("credencial", "carnet", "tarjeta de cobertura", "constancia de afiliacion"),
    "afiliacion": ("afiliacion", "afiliado", "membresia", "socio", "beneficiario"),
    "inactiva": ("inactiva", "dado de baja", "cancelada", "cancelado", "vencida", "caducada", "sin vigencia"),
    "verificacion": ("verificar", "validar", "comprobar", "chequear", "consultar estado", "confirmar vigencia"),
    "autorizacion": ("autorizacion", "aprobacion", "permiso", "validacion previa", "conformidad"),
    "notificacion": ("notificar", "avisar", "comunicar", "mandar aviso", "informar a la entidad"),
    "servicio_social": ("servicio social", "asistencia social", "trabajo social", "area social"),
    "cobertura_publica": ("cobertura publica", "proteccion publica", "seguro estatal", "cobertura del estado"),
    "pago": ("pago", "dinero", "garantia", "deposito", "anticipo"),
    "accidente_laboral": ("accidente laboral", "accidente de trabajo", "siniestro laboral", "lesion laboral", "durante la jornada"),
    "accidente_trayecto": ("accidente de trayecto", "yendo al trabajo", "volviendo del trabajo", "in itinere"),
    "art": ("art", "aseguradora de riesgos", "riesgos del trabajo", "cobertura laboral"),
    "numero_afiliado": ("numero de afiliado", "numero de socio", "identificador de afiliacion", "numero de miembro"),
    "digito_reservado": ("digito reservado", "terminacion reservada", "numero especial", "digito especial"),
    "dolor_toracico": ("dolor toracico", "dolor de pecho", "opresion precordial", "molestia en el pecho", "dolor en el corazon"),
    "ecg": ("ecg", "electrocardiograma", "electro", "trazado cardiaco", "estudio cardiaco de 12 derivaciones"),
    "acv": ("acv", "accidente cerebrovascular", "derrame cerebral", "evento cerebrovascular", "ictus"),
    "focal_neurologico": ("signos neurologicos", "debilidad de un lado", "cara torcida", "boca desviada", "perdida de fuerza", "habla dificultosa"),
    "ultima_vez_bien": ("ultima hora en que estuvo bien", "ultima vez visto bien", "ultimo momento normal", "hora de inicio desconocida"),
    "sepsis": ("sepsis", "infeccion sistemica", "cuadro septico", "infeccion generalizada"),
    "shock": ("shock", "choque", "inestabilidad hemodinamica", "presion muy baja"),
    "hemocultivo": ("hemocultivo", "cultivo de sangre", "muestra para cultivo"),
    "antimicrobiano": ("antimicrobiano", "antibiotico", "tratamiento antiinfeccioso"),
    "ambulancia": ("ambulancia", "movil sanitario", "transporte sanitario", "unidad de emergencias", "traslado prehospitalario"),
    "plazo": ("plazo", "tiempo", "demora", "limite", "ventana", "dentro de cuantos minutos"),
    "derivacion": ("derivacion", "derivar", "traslado", "transferencia", "remision"),
    "establecimiento": ("establecimiento", "institucion receptora", "destino", "hospital receptor", "prestador", "clinica"),
    "internacion": ("internacion", "internar", "hospitalizacion", "ingreso hospitalario"),
    "cama": ("cama", "plaza", "cupo", "disponibilidad", "lugar de internacion"),
    "sector": ("sector", "unidad coronaria", "terapia intensiva", "sala general", "servicio de internacion"),
    "aislamiento": ("aislamiento", "precauciones", "separacion sanitaria"),
    "aereo": ("aereo", "aerosoles", "presion negativa", "tuberculosis", "sarampion", "varicela"),
    "contacto_gotas": ("contacto", "gotas", "cohorte", "transmision por contacto", "transmision por gotas"),
    "habitacion": ("habitacion", "cuarto", "dormitorio", "pieza"),
    "retriage": ("retriage", "reclasificacion", "nueva clasificacion", "reevaluacion de enfermeria", "volver a clasificar"),
    "evaluacion_medica": ("evaluacion medica", "consulta medica", "ver al medico", "atencion del doctor"),
}


def _marcadores_conceptuales(texto: str) -> set[str]:
    normalizado = _sin_acentos(texto)
    return {
        f"cx{concepto.replace('_', '')}"
        for concepto, expresiones in CONCEPTOS.items()
        if any(_sin_acentos(expresion) in normalizado for expresion in expresiones)
    }


def _texto_semantico(texto: str) -> str:
    marcadores = sorted(_marcadores_conceptuales(texto))
    # Repetición moderada para que el concepto compita con las palabras crudas.
    return f"{texto} {' '.join(marcadores)} {' '.join(marcadores)}"


def _tokens_semanticos(texto: str) -> list[str]:
    tokens = _tokens(_texto_semantico(texto))
    # Bigramas genéricos: preservan expresiones como registro provisorio.
    bigramas = [f"bg{a}{b}" for a, b in zip(tokens, tokens[1:]) if not a.startswith("bg")]
    return tokens + bigramas


class BuscadorNormativoSemantico:
    """Recuperador documental híbrido con expansión conceptual no dirigida."""

    # Modo orientado a recall: el agente recibe las tres normas mejor
    # posicionadas. No depende del vocabulario ni del tipo de consulta.
    k_entorno = 3

    def __init__(self, ruta_normas: str | Path):
        self.fragmentos = _fragmentar_normas(Path(ruta_normas))
        agrupados: dict[str, list[Fragmento]] = defaultdict(list)
        for fragmento in self.fragmentos:
            agrupados[fragmento.seccion].append(fragmento)
        self.codigos = sorted(agrupados)
        self.secciones = {
            codigo: self._armar_seccion(codigo, agrupados[codigo])
            for codigo in self.codigos
        }
        self._indice_seccion = {codigo: indice for indice, codigo in enumerate(self.codigos)}
        self._indices_fragmentos: dict[str, list[int]] = defaultdict(list)
        for indice, fragmento in enumerate(self.fragmentos):
            self._indices_fragmentos[fragmento.seccion].append(indice)

        textos_seccion = [self.secciones[codigo].texto for codigo in self.codigos]
        textos_fragmento = [fragmento.texto for fragmento in self.fragmentos]
        textos_titulo = [agrupados[codigo][0].titulo for codigo in self.codigos]
        self._tokens_seccion = [_tokens_semanticos(texto) for texto in textos_seccion]
        self._tokens_fragmento = [_tokens_semanticos(texto) for texto in textos_fragmento]
        self._tokens_titulo = [_tokens_semanticos(texto) for texto in textos_titulo]
        self._conceptos_seccion = [_marcadores_conceptuales(texto) for texto in textos_seccion]

        self._bm25_seccion = _BM25(self._tokens_seccion)
        self._bm25_fragmento = _BM25(self._tokens_fragmento)
        self._bm25_titulo = _BM25(self._tokens_titulo, k1=1.2, b=0.3)
        self._caracteres_seccion = _IndiceCaracteres([_texto_semantico(t) for t in textos_seccion])
        self._caracteres_fragmento = _IndiceCaracteres([_texto_semantico(t) for t in textos_fragmento])
        self._referencias = {
            codigo: {
                referencia
                for referencia in re.findall(r"NOR-[A-Z]{3}-\d+", self.secciones[codigo].texto)
                if referencia in self.secciones and referencia != codigo
            }
            for codigo in self.codigos
        }

    @staticmethod
    def _armar_seccion(codigo: str, fragmentos: list[Fragmento]) -> SeccionRecuperada:
        titulo = fragmentos[0].titulo
        cuerpo = "\n\n".join(fragmento.parrafo for fragmento in fragmentos)
        valores: list[str] = []
        for fragmento in fragmentos:
            if "\nValores: " in fragmento.texto:
                linea = fragmento.texto.rsplit("\nValores: ", 1)[1].removesuffix(".")
                valores.extend(valor.strip() for valor in linea.split(";") if valor.strip())
        valores = list(dict.fromkeys(valores))
        linea_valores = f"\n\nValores: {'; '.join(valores)}." if valores else ""
        return SeccionRecuperada(codigo, f"{titulo}\n\n{cuerpo}{linea_valores}")

    def _puntajes_secciones(self, consulta: str) -> dict[str, float]:
        tokens = _tokens_semanticos(consulta)
        conceptos = _marcadores_conceptuales(consulta)
        consulta_semantica = _texto_semantico(consulta)
        bm25_seccion = {
            codigo: self._bm25_seccion.puntuar(tokens, self._indice_seccion[codigo])
            for codigo in self.codigos
        }
        bm25_fragmento = {
            codigo: max(self._bm25_fragmento.puntuar(tokens, i) for i in self._indices_fragmentos[codigo])
            for codigo in self.codigos
        }
        bm25_titulo = {
            codigo: self._bm25_titulo.puntuar(tokens, self._indice_seccion[codigo])
            for codigo in self.codigos
        }
        todos_caracteres_seccion = self._caracteres_seccion.puntuar_todos(consulta_semantica)
        todos_caracteres_fragmento = self._caracteres_fragmento.puntuar_todos(consulta_semantica)
        caracteres_seccion = {
            codigo: todos_caracteres_seccion[self._indice_seccion[codigo]]
            for codigo in self.codigos
        }
        caracteres_fragmento = {
            codigo: max(
                todos_caracteres_fragmento[i]
                for i in self._indices_fragmentos[codigo]
            )
            for codigo in self.codigos
        }
        cobertura = {
            codigo: len(conceptos & self._conceptos_seccion[self._indice_seccion[codigo]]) / max(len(conceptos), 1)
            for codigo in self.codigos
        }
        señales = [
            (_normalizar_puntajes(bm25_seccion), 0.28),
            (_normalizar_puntajes(bm25_fragmento), 0.25),
            (_normalizar_puntajes(bm25_titulo), 0.08),
            (_normalizar_puntajes(caracteres_seccion), 0.14),
            (_normalizar_puntajes(caracteres_fragmento), 0.12),
            (_normalizar_puntajes(cobertura), 0.13),
        ]
        return {
            codigo: sum(valores[codigo] * peso for valores, peso in señales)
            for codigo in self.codigos
        }

    def _ranking_secciones(self, consulta: str) -> list[tuple[float, SeccionRecuperada]]:
        puntajes = self._puntajes_secciones(consulta)
        return sorted(
            ((puntajes[codigo], self.secciones[codigo]) for codigo in self.codigos),
            key=lambda par: (-par[0], par[1].seccion),
        )

    @staticmethod
    def _segmentos(consulta: str) -> list[str]:
        partes = re.split(r"[;:.?]|\b(?:y|pero|aunque|ademas|con)\b", _sin_acentos(consulta))
        return [parte.strip() for parte in partes if len(_tokens_semanticos(parte)) >= 2]

    def _necesita_segunda(
        self,
        consulta: str,
        ranking: list[tuple[float, SeccionRecuperada]],
    ) -> bool:
        if len(ranking) < 2 or ranking[0][0] <= 0:
            return False
        primero, segundo = ranking[0], ranking[1]
        relacion = segundo[0] / primero[0]
        if relacion >= 0.74:
            return True

        conceptos = _marcadores_conceptuales(consulta)
        conceptos_primero = self._conceptos_seccion[self._indice_seccion[primero[1].seccion]]
        conceptos_segundo = self._conceptos_seccion[self._indice_seccion[segundo[1].seccion]]
        pendientes = conceptos - conceptos_primero
        cobertura_marginal = len(pendientes & conceptos_segundo) / max(len(conceptos), 1)
        if relacion >= 0.46 and cobertura_marginal >= 0.18:
            return True

        ganadores = []
        for segmento in self._segmentos(consulta):
            puntajes = self._puntajes_secciones(segmento)
            ganador, valor = max(puntajes.items(), key=lambda par: par[1])
            if valor >= 0.38:
                ganadores.append(ganador)
        if primero[1].seccion in ganadores and segundo[1].seccion in ganadores:
            return True

        relacionados = self._referencias[primero[1].seccion] | {
            codigo for codigo, referencias in self._referencias.items() if primero[1].seccion in referencias
        }
        return segundo[1].seccion in relacionados and relacion >= 0.52

    def _ranking_fragmentos(self, consulta: str) -> list[tuple[float, Fragmento]]:
        tokens = _tokens_semanticos(consulta)
        conceptos = _marcadores_conceptuales(consulta)
        consulta_semantica = _texto_semantico(consulta)
        bm25 = {
            str(i): self._bm25_fragmento.puntuar(tokens, i)
            for i in range(len(self.fragmentos))
        }
        caracteres = {
            str(i): valor
            for i, valor in enumerate(self._caracteres_fragmento.puntuar_todos(consulta_semantica))
        }
        cobertura = {
            str(i): len(conceptos & _marcadores_conceptuales(fragmento.texto)) / max(len(conceptos), 1)
            for i, fragmento in enumerate(self.fragmentos)
        }
        bm25 = _normalizar_puntajes(bm25)
        caracteres = _normalizar_puntajes(caracteres)
        cobertura = _normalizar_puntajes(cobertura)
        return sorted(
            (
                (
                    0.58 * bm25[str(i)] + 0.24 * caracteres[str(i)] + 0.18 * cobertura[str(i)],
                    fragmento,
                )
                for i, fragmento in enumerate(self.fragmentos)
            ),
            key=lambda par: (-par[0], par[1].seccion, par[1].orden),
        )

    def recuperar(self, consulta: str, k: int) -> list[SeccionRecuperada | Fragmento]:
        if not isinstance(consulta, str) or not consulta.strip() or k <= 0:
            return []
        if k <= self.k_entorno:
            ranking = self._ranking_secciones(consulta)
            if k >= 3:
                return [documento for _, documento in ranking[:k]]
            limite = 2 if self._necesita_segunda(consulta, ranking) else 1
            return [documento for _, documento in ranking[: min(k, limite)]]
        return [fragmento for _, fragmento in self._ranking_fragmentos(consulta)[:k]]


def construir_buscador(ruta_normas: str | Path) -> BuscadorNormativoSemantico:
    return BuscadorNormativoSemantico(ruta_normas)
