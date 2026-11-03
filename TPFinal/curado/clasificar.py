"""Genera una clasificación provisional y su trazabilidad a partir del historial."""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from curado.reglas import cobertura, evaluar_fila, extraer_cobertura, normalizar, parametros


def doble_credencial(fila, p):
    """La costumbre decide preferencia; las normas se aplican a la credencial efectivamente verificada."""
    if normalizar(fila.get("lesion_trabajo")) != "no" or ";" not in fila.get("credenciales", ""):
        return None
    partes = fila["credenciales"].split(";")
    datos = [extraer_cobertura(parte) for parte in partes]
    if len(datos) != 2 or any(d is None for d in datos) or {d[2] for d in datos} != {"prepaga", "obra_social"}:
        return {"pendientes": ["No se pueden interpretar las dos credenciales."], "ruido": [], "reglas": []}
    seleccion = [i for i, d in enumerate(datos) if normalizar(d[0]) == normalizar(fila.get("entidad_verificada"))]
    if len(seleccion) != 1:
        return {"pendientes": ["La entidad verificada no identifica una de las credenciales."], "ruido": [], "reglas": []}
    indice = seleccion[0]
    # No suponemos cuál sería el estado de la prepaga si se verificó la obra social.
    elegida = dict(fila, credenciales=partes[indice].strip())
    normas = cobertura(elegida, p)
    ruido = ["eligio_obra_social_con_prepaga"] if datos[indice][2] == "obra_social" else []
    return {"pendientes": [], "ruido": ruido, "reglas": normas}


def clasificar_fila(fila, p):
    resultados = evaluar_fila(fila, p)
    doble = doble_credencial(fila, p)
    ruido, pendientes = [], []
    if doble is not None:
        # Sustituye solo las insuficiencias por dos credenciales, preservando las demás normas.
        resultados = [r for r in resultados if "Hay varias credenciales" not in r.detalle] + doble["reglas"]
        ruido.extend(doble["ruido"])
        pendientes.extend(doble["pendientes"])
    violaciones = [r for r in resultados if r.estado == "violacion"]
    pendientes.extend(f"{r.regla}: {r.detalle}" for r in resultados if r.estado == "insuficiente")
    try:
        edad = int(fila["edad"])
        aviso = normalizar(fila["aviso_al_voluntariado"])
        if aviso not in ("si", "no"):
            raise ValueError("aviso desconocido")
        esperado = edad >= 75 and not fila.get("acompanante", "").strip()
        if (aviso == "si") != esperado:
            ruido.append("voluntariado_difiere_costumbre")
    except (KeyError, TypeError, ValueError):
        pendientes.append("No se pudo evaluar la costumbre de voluntariado.")
    # El patrón de box de fase 4 es exploratorio; no se usa para asignar ruido.
    tipo = "error" if violaciones else "ruido" if ruido else "correcta"
    return {"id": fila["id"], "tipo": tipo, "revisar": bool(pendientes), "motivos_ruido": ruido,
            "violaciones": [r.diccionario() for r in violaciones], "pendientes": pendientes,
            "comparaciones_normativas": [r.diccionario() for r in resultados]}


def sha(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historial", type=Path, default=Path("historial/historial.csv"))
    parser.add_argument("--parametros", type=Path, default=Path("normas/original/parametros.yaml"))
    parser.add_argument("--salida", type=Path, default=Path("historial_clasificado.csv"))
    parser.add_argument("--trazas", type=Path, default=Path("resultados/trazas_clasificacion.jsonl"))
    parser.add_argument("--resumen", type=Path, default=Path("resultados/resumen_clasificacion.json"))
    args = parser.parse_args()
    p = parametros(args.parametros)
    with args.historial.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    ids = [f["id"] for f in filas]
    if len(ids) != len(set(ids)) or any(not i for i in ids):
        parser.error("El historial contiene IDs vacíos o repetidos.")
    resultados = [clasificar_fila(fila, p) for fila in filas]
    for ruta in (args.trazas, args.resumen):
        ruta.parent.mkdir(parents=True, exist_ok=True)
    with args.trazas.open("w", encoding="utf-8", newline="\n") as archivo:
        for r in resultados:
            archivo.write(json.dumps(r, ensure_ascii=False) + "\n")
    pendientes = [r["id"] for r in resultados if r["revisar"]]
    if pendientes:
        parser.error(f"Hay {len(pendientes)} filas pendientes de revisión; no se actualizó el CSV. Ver {args.trazas}.")
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", encoding="utf-8", newline="") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=["id", "tipo"])
        writer.writeheader()
        writer.writerows({"id": r["id"], "tipo": r["tipo"]} for r in resultados)
    resumen = {"total": len(resultados), "tipos": dict(sorted(Counter(r["tipo"] for r in resultados).items())),
               "filas_pendientes_revision": sum(r["revisar"] for r in resultados),
               "motivos_ruido": dict(sorted(Counter(m for r in resultados for m in r["motivos_ruido"]).items())),
               "sha256": {str(ruta): sha(ruta) for ruta in
                          (args.historial, args.parametros, Path("curado/reglas.py"), Path("curado/clasificar.py"), args.salida)}}
    args.resumen.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
