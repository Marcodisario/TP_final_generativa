"""Convierte las trazas del historial clasificadas como correctas en conversaciones JSONL.

El prompt es la referencia de la cátedra, todavía sin optimizar. No genera casos nuevos.
"""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from admision.ejemplo import mensaje_de_sistema, primer_mensaje


HERRAMIENTAS = {"leer_triage", "preguntar", "verificar_afiliacion", "buscar_normativa", "registrar_decision"}
CAMPOS = ("registro", "numero_documento", "box_antes_del_registro", "circuito", "plazo_circuito_min",
          "cobertura", "entidad_a_notificar", "aviso_al_voluntariado")


def sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def leer_csv(ruta):
    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def leer_jsonl(ruta):
    registros = []
    with Path(ruta).open(encoding="utf-8-sig") as archivo:
        for numero, linea in enumerate(archivo, 1):
            if not linea.strip():
                raise ValueError(f"{ruta}: línea {numero} vacía")
            try:
                registros.append(json.loads(linea))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{ruta}: JSON inválido en la línea {numero}") from exc
    return registros


def indices_unicos(registros, nombre):
    indice = {}
    for registro in registros:
        ident = registro.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in indice:
            raise ValueError(f"{nombre}: id vacío, inválido o duplicado: {ident!r}")
        indice[ident] = registro
    return indice


def valor_csv(valor):
    if valor is True:
        return "sí"
    if valor is False:
        return "no"
    return "" if valor is None else str(valor).strip()


def validar_traza(traza, fila):
    ident, paciente, pasos = traza["id"], traza.get("paciente_id"), traza.get("pasos")
    if not isinstance(paciente, str) or not paciente.strip() or not isinstance(pasos, list) or not pasos:
        raise ValueError(f"{ident}: faltan paciente_id o pasos")
    if not isinstance(traza.get("ficha"), dict) or set(traza["ficha"]) != set(CAMPOS):
        raise ValueError(f"{ident}: ficha incompleta o con campos inesperados")
    for i, paso in enumerate(pasos, 1):
        if not isinstance(paso, dict) or paso.get("orden") != i:
            raise ValueError(f"{ident}: orden inválido en el paso {i}")
        herramienta, argumentos = paso.get("herramienta"), paso.get("argumentos")
        if herramienta not in HERRAMIENTAS or not isinstance(argumentos, dict) or not isinstance(paso.get("resultado"), str):
            raise ValueError(f"{ident}: paso {i} inválido")
        if "paciente_id" in argumentos and argumentos["paciente_id"] != paciente:
            raise ValueError(f"{ident}: paciente_id inconsistente en paso {i}")
        if herramienta == "registrar_decision" and i != len(pasos):
            raise ValueError(f"{ident}: existen pasos posteriores a registrar_decision")
        if paso["resultado"].startswith("Error:"):
            raise ValueError(f"{ident}: error de herramienta en paso {i}")
    if pasos[0]["herramienta"] != "leer_triage" or pasos[-1]["herramienta"] != "registrar_decision":
        raise ValueError(f"{ident}: la traza debe empezar leyendo triage y terminar registrando")
    if any(pasos[-1]["argumentos"].get(campo) != traza["ficha"][campo] for campo in CAMPOS):
        raise ValueError(f"{ident}: ficha y argumentos de registrar_decision no coinciden")
    diferencias = [campo for campo in CAMPOS if valor_csv(traza["ficha"][campo]) != fila[campo].strip()]
    if diferencias:
        raise ValueError(f"{ident}: ficha distinta del historial: {', '.join(diferencias)}")
    verificaciones = [p["argumentos"] for p in pasos if p["herramienta"] == "verificar_afiliacion"]
    esperada = (fila["entidad_verificada"], fila["numero_verificado"])
    obtenidas = [(v.get("entidad", ""), v.get("numero_afiliado", "")) for v in verificaciones]
    if obtenidas != ([esperada] if any(esperada) else []):
        raise ValueError(f"{ident}: verificación distinta del historial")


def convertir_traza(traza, sistema):
    mensajes = [{"role": "system", "content": sistema},
                {"role": "user", "content": primer_mensaje(traza["paciente_id"])}]
    for paso in traza["pasos"]:
        llamada = {"herramienta": paso["herramienta"], "argumentos": paso["argumentos"]}
        mensajes.append({"role": "assistant", "content": json.dumps(llamada, ensure_ascii=False)})
        if paso["herramienta"] != "registrar_decision":
            mensajes.append({"role": "user", "content": f"Resultado de {paso['herramienta']}:\n{paso['resultado']}"})
    return {"id": traza["id"], "paciente_id": traza["paciente_id"], "messages": mensajes}


def preparar(historial, clasificacion, trazas):
    filas = leer_csv(historial)
    etiquetas = leer_csv(clasificacion)
    originales = leer_jsonl(trazas)
    por_id = indices_unicos(filas, str(historial))
    por_etiqueta = indices_unicos(etiquetas, str(clasificacion))
    por_traza = indices_unicos(originales, str(trazas))
    if set(por_id) != set(por_etiqueta) or set(por_id) != set(por_traza):
        raise ValueError("Los IDs de historial, clasificación y trazas no coinciden exactamente")
    if any(set(e) != {"id", "tipo"} or e["tipo"] not in {"correcta", "error", "ruido"} for e in etiquetas):
        raise ValueError("La clasificación debe tener solo id,tipo y etiquetas válidas")
    sistema = mensaje_de_sistema()
    conversaciones = []
    for traza in originales:
        if por_etiqueta[traza["id"]]["tipo"] == "correcta":
            validar_traza(traza, por_id[traza["id"]])
            conversaciones.append(convertir_traza(traza, sistema))
    return conversaciones, Counter(e["tipo"] for e in etiquetas), sistema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historial", type=Path, default=Path("historial/historial.csv"))
    parser.add_argument("--clasificacion", type=Path, default=Path("historial_clasificado.csv"))
    parser.add_argument("--trazas", type=Path, default=Path("historial/trazas.jsonl"))
    parser.add_argument("--salida", type=Path, default=Path("entrenamiento/conversaciones_historial.jsonl"))
    parser.add_argument("--resumen", type=Path, default=Path("entrenamiento/resumen_conversion.json"))
    args = parser.parse_args()
    entradas = (args.historial, args.clasificacion, args.trazas)
    salidas = (args.salida, args.resumen)
    if len({p.resolve() for p in (*entradas, *salidas)}) != len(entradas) + len(salidas):
        parser.error("Las rutas de entrada y salida deben ser distintas")
    conversaciones, cantidades, sistema = preparar(*entradas)
    for ruta in salidas:
        ruta.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", encoding="utf-8", newline="\n") as archivo:
        for conversacion in conversaciones:
            archivo.write(json.dumps(conversacion, ensure_ascii=False) + "\n")
    resumen = {"clasificacion": "aceptada como definitiva por el grupo", "criterio": "solo filas etiquetadas correcta",
               "etiquetas": dict(sorted(cantidades.items())), "conversaciones": len(conversaciones),
               "prompt": "admision.ejemplo.mensaje_de_sistema; referencia sin optimizar",
               "prompt_sha256": hashlib.sha256(sistema.encode("utf-8")).hexdigest(),
               "sha256": {nombre: sha256(ruta) for nombre, ruta in {
                   "historial": args.historial, "clasificacion": args.clasificacion, "trazas": args.trazas,
                   "convertidor": Path(__file__), "agente_ejemplo": Path("admision/ejemplo.py"),
                   "conversaciones": args.salida}.items()}}
    args.resumen.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
