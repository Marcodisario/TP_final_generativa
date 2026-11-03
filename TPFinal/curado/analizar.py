"""Explora reglas por ID o genera un reporte JSONL; no produce la clasificación final."""
import argparse
import csv
import json
from pathlib import Path

from curado.reglas import evaluar_fila, parametros


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historial", type=Path, default=Path("historial/historial.csv"))
    parser.add_argument("--parametros", type=Path, default=Path("normas/original/parametros.yaml"))
    parser.add_argument("--id", help="Mostrar solo una admisión, por ejemplo H-0001")
    parser.add_argument("--salida", type=Path, help="Guardar resultados detallados en JSONL")
    args = parser.parse_args()
    p = parametros(args.parametros)
    with args.historial.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    if args.id:
        filas = [fila for fila in filas if fila["id"] == args.id]
        if not filas:
            parser.error(f"No se encontró el ID {args.id}")
    resultados = [{"id": fila["id"], "reglas": [r.diccionario() for r in evaluar_fila(fila, p)]} for fila in filas]
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        with args.salida.open("w", encoding="utf-8", newline="\n") as archivo:
            for resultado in resultados:
                archivo.write(json.dumps(resultado, ensure_ascii=False) + "\n")
        print(f"Reporte guardado: {args.salida} ({len(resultados)} filas)")
    else:
        for resultado in resultados:
            print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
