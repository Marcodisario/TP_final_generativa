"""Comprueba reglas escritas sobre una fila; no identifica costumbres ni clasifica ruido."""

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import unicodedata

import yaml


@dataclass(frozen=True)
class Resultado:
    regla: str
    norma: str
    estado: str  # violacion, compatible o insuficiente
    detalle: str

    def diccionario(self):
        return asdict(self)


def parametros(ruta: Path):
    with Path(ruta).open(encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo)
    return {p["codigo"]: int(p["valor"]) for p in datos["parametros"]}


def normalizar(valor):
    texto = unicodedata.normalize("NFD", str(valor or "").strip().lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


def comparar(regla, norma, observado, esperado, campo):
    estado = "compatible" if normalizar(observado) == normalizar(esperado) else "violacion"
    return Resultado(regla, norma, estado, f"{campo}: observado={observado!r}; esperado={esperado!r}")


def insuficiente(regla, norma, detalle):
    return Resultado(regla, norma, "insuficiente", detalle)


def entero(valor):
    try:
        return int(valor)
    except (ValueError, TypeError):
        return None


def identidad_y_box(fila, p):
    resultados = []
    tipo, numero = fila.get("documento_tipo", ""), fila.get("documento_numero", "")
    nivel, edad = entero(fila.get("nivel")), entero(fila.get("edad"))
    doc = normalizar(tipo)
    norma = "NOR-ADM-01 §2–3; NOR-ADM-03 §1–3"
    if not tipo and not numero:
        esperado = "provisorio"
    elif not tipo or not numero or doc not in ("dni", "pasaporte", "cedula"):
        esperado = None
    elif doc in ("pasaporte", "cedula") and nivel is None:
        esperado = None
    elif doc in ("pasaporte", "cedula") and nivel <= p["P-ADM-3"]:
        esperado = "provisorio"
    else:
        esperado = "definitivo"
    if esperado is None:
        resultados.append(insuficiente("tipo_registro", norma, "Documento o nivel incompleto o no reconocido."))
    else:
        resultados.append(comparar("tipo_registro", norma, fila.get("registro", ""), esperado, "registro"))
    if bool(tipo) != bool(numero):
        resultados.append(insuficiente("numero_documento", norma, "Tipo y número de documento inconsistentes en los datos iniciales."))
    else:
        resultados.append(comparar("numero_documento", norma, fila.get("numero_documento", ""), numero, "numero_documento"))

    norma_box = "NOR-ADM-01 §4; NOR-ADM-02 §1–2"
    observado = normalizar(fila.get("box_antes_del_registro"))
    if (edad is not None and edad >= p["P-ADM-2"]) or (nivel is not None and nivel <= p["P-ADM-1"]):
        resultados.append(comparar("box", norma_box, observado, "si", "box_antes_del_registro"))
    elif edad is None or nivel is None or observado not in ("si", "no"):
        resultados.append(insuficiente("box", norma_box, "Edad, nivel o respuesta de box ausente o no reconocida."))
    else:
        resultados.append(Resultado("box", norma_box, "compatible", "La norma no exige que el box preceda al registro en este caso."))
    return resultados


def circuitos(fila, p):
    motivo, sepsis = normalizar(fila.get("motivo")), normalizar(fila.get("sospecha_sepsis"))
    llegada = normalizar(fila.get("llegada"))
    norma = "NOR-TDE-01–04"
    if sepsis not in ("no", "probable", "con signos de shock", "posible, sin signos de shock"):
        return [insuficiente("circuito", norma, "Categoría de sepsis ausente o no reconocida."),
                insuficiente("plazo", norma, "No se puede determinar el circuito esperado.")]
    # Si hay señales contradictorias no se inventa una prioridad entre circuitos.
    candidatos = []
    if motivo == "dolor toracico":
        candidatos.append(("ecg", p["P-TDE-1"]))
    if motivo == "signos neurologicos focales de inicio subito":
        candidatos.append(("codigo_acv", p["P-TDE-2"]))
    if sepsis != "no":
        candidatos.append(("codigo_sepsis", p["P-TDE-4"] if sepsis == "posible, sin signos de shock" else p["P-TDE-3"]))
    if not motivo or (motivo == "sospecha de sepsis" and sepsis == "no") or len(candidatos) > 1:
        return [insuficiente("circuito", norma, "Triage ausente o señales de circuitos contradictorias."),
                insuficiente("plazo", norma, "No se puede determinar el circuito esperado.")]
    esperado, plazo = candidatos[0] if candidatos else ("ninguno", None)
    resultados = [comparar("circuito", norma, fila.get("circuito", ""), esperado, "circuito")]
    if plazo is not None and llegada not in ("en ambulancia", "por sus propios medios"):
        resultados.append(insuficiente("plazo", norma, "Forma de llegada ausente o no reconocida."))
    else:
        if plazo is not None and llegada == "en ambulancia":
            plazo -= p["P-TDE-5"]
        observado = fila.get("plazo_circuito_min", "")
        resultados.append(comparar("plazo", norma, observado, "" if plazo is None else str(plazo), "plazo_circuito_min"))
    return resultados


def extraer_cobertura(texto):
    # Formato del historial: Nombre (obra social|prepaga) número; se conservan ceros y separadores.
    # No absorber una credencial anterior dentro del nombre de la siguiente.
    m = re.fullmatch(r"\s*([^;()]+?)\s+\((obra social|prepaga)\)\s+(\S+)\s*", texto, re.IGNORECASE)
    return (m.group(1), m.group(3), m.group(2).lower().replace(" ", "_")) if m else None


def cobertura(fila, p):
    norma = "NOR-COB-01–04"
    trabajo = normalizar(fila.get("lesion_trabajo"))
    if trabajo not in ("no", "trabajando", "en el trayecto"):
        return [insuficiente("cobertura", norma, "Situación laboral desconocida.")]
    laboral = trabajo != "no"
    fuente = (fila.get("art_declarada") or "") if laboral else ((fila.get("credenciales") or "") or (fila.get("cobertura_declarada") or ""))
    if not laboral and ";" in fuente:
        detalle = "Hay varias credenciales; la norma no define aquí cuál elegir. Revisar la costumbre y la selección."
        return [insuficiente(regla, norma, detalle) for regla in
                ("entidad_verificada", "numero_verificado", "cobertura", "notificacion")]
    if laboral:
        m = re.fullmatch(r"\s*(.+?)\s+CUIL\s+(\S+)\s*", fuente, re.IGNORECASE)
        datos = (m.group(1), m.group(2), "art") if m else None
    else:
        datos = extraer_cobertura(fuente)
    sin_cobertura = not laboral and (normalizar(fuente) == "ninguna" or
        (not fuente and normalizar(fila.get("puede_responder")) == "no" and not fila.get("acompanante")))
    if sin_cobertura:
        return [comparar("cobertura", norma, fila.get("cobertura", ""), "sin_cobertura", "cobertura"),
                comparar("notificacion", norma, fila.get("entidad_a_notificar", ""), "", "entidad_a_notificar")]
    if not datos:
        return [insuficiente("verificacion", norma, "No se pudo determinar la entidad y el número de origen."),
                insuficiente("cobertura", norma, "No se pudo determinar la cobertura de origen."),
                insuficiente("notificacion", norma, "No se pudo determinar la entidad de origen.")]
    entidad, numero, tipo = datos
    ver_entidad, ver_numero = fila.get("entidad_verificada", ""), fila.get("numero_verificado", "")
    resultados = [comparar("entidad_verificada", "NOR-COB-02 §2, §5; NOR-COB-04 §2", ver_entidad, entidad, "entidad_verificada"),
                  comparar("numero_verificado", "NOR-COB-02 §2, §5; NOR-COB-04 §2", ver_numero, numero, "numero_verificado")]
    verifico_bien = normalizar(ver_entidad) == normalizar(entidad) and normalizar(ver_numero) == normalizar(numero)
    respuesta = normalizar(fila.get("respuesta_verificacion"))
    reservado = not laboral and numero[-1:] == str(p["P-COB-2"])
    if reservado:
        esperado, notificar = "sin_cobertura", entidad
    elif laboral:
        # La norma prioriza ART; el estado de la afiliación no permite inferir una alternativa.
        esperado, notificar = "art", entidad
    elif verifico_bien and respuesta in ("activa", "inactiva"):
        esperado, notificar = (tipo, entidad) if respuesta == "activa" else ("sin_cobertura", "")
    else:
        resultados.extend([insuficiente("cobertura", norma, "No se conoce la respuesta válida de la entidad y número correctos."),
                           insuficiente("notificacion", norma, "No se conoce la respuesta válida de la entidad y número correctos.")])
        return resultados
    resultados.extend([comparar("cobertura", norma, fila.get("cobertura", ""), esperado, "cobertura"),
                       comparar("notificacion", norma, fila.get("entidad_a_notificar", ""), notificar, "entidad_a_notificar")])
    return resultados


def evaluar_fila(fila, p):
    """Los resultados presuponen que el CSV refleja la situación pertinente al registrar."""
    return identidad_y_box(fila, p) + circuitos(fila, p) + cobertura(fila, p)
