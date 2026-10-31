"""Ejecuta la evaluación oficial del RAG y guarda un artefacto auditable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from admision.contrato import cargar_entrega
from admision.evaluar_rag import cargar_dataset, evaluar_buscador, evaluar_recuperador


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrega", type=Path, required=True)
    parser.add_argument("--normas", type=Path, required=True)
    parser.add_argument("--consultas", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()

    buscador = cargar_entrega(args.entrega).construir_buscador(args.normas)
    dataset = cargar_dataset(args.consultas)
    resultado = {
        "entradas": {
            "entrega": str(args.entrega),
            "normas": str(args.normas),
            "consultas": str(args.consultas),
        },
        "entorno": evaluar_buscador(buscador, dataset),
        "presupuesto": [
            evaluar_recuperador(buscador.recuperar, dataset, presupuesto)
            for presupuesto in (256, 512, 1024)
        ],
    }

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

