"""Resume el análisis normativo sin asignar etiquetas finales al historial."""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from curado.reglas import evaluar_fila, parametros


def sha256(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def analizar(historial, ruta_parametros):
    p = parametros(ruta_parametros)
    with historial.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    detalle, conteo_reglas, conteo_estados = [], Counter(), Counter()
    for fila in filas:
        reglas = evaluar_fila(fila, p)
        violaciones = [r for r in reglas if r.estado == "violacion"]
        pendientes = [r for r in reglas if r.estado == "insuficiente"]
        estado = "candidata_error" if violaciones else "pendiente" if pendientes else "sin_alertas"
        conteo_estados[estado] += 1
        conteo_reglas.update(r.regla for r in violaciones)
        detalle.append({"id": fila["id"], "estado_revision": estado,
                        "violaciones": "; ".join(r.regla for r in violaciones),
                        "normas": "; ".join(dict.fromkeys(r.norma for r in violaciones)),
                        "detalles": " | ".join(r.detalle for r in violaciones),
                        "pendientes": "; ".join(r.regla for r in pendientes)})
    resumen = {"filas": len(filas), "por_estado_revision": dict(sorted(conteo_estados.items())),
               "violaciones_por_regla": dict(sorted(conteo_reglas.items())),
               "filas_con_insuficientes": sum(bool(x["pendientes"]) for x in detalle),
               "sha256": {"historial": sha256(historial), "parametros": sha256(ruta_parametros),
                          "reglas_py": sha256(Path(__file__).with_name("reglas.py"))}}
    return detalle, resumen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historial", type=Path, default=Path("historial/historial.csv"))
    parser.add_argument("--parametros", type=Path, default=Path("normas/original/parametros.yaml"))
    parser.add_argument("--salida", type=Path, default=Path("resultados/revision_normativa.csv"))
    parser.add_argument("--resumen", type=Path, default=Path("resultados/resumen_revision.json"))
    args = parser.parse_args()
    detalle, resumen = analizar(args.historial, args.parametros)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.resumen.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=["id", "estado_revision", "violaciones", "normas", "detalles", "pendientes"])
        escritor.writeheader()
        escritor.writerows(detalle)
    args.resumen.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"Detalle: {args.salida}; resumen: {args.resumen}")


if __name__ == "__main__":
    main()
