"""Compara los tres RAG sobre las consultas oficiales y el holdout nuevo."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from pathlib import Path

from admision.evaluar_rag import (
    _normalizar,
    cargar_dataset,
    evaluar_buscador,
    evaluar_recuperador,
)
from buscador_rag import BuscadorNormativo
from buscador_rag_embeddings import BuscadorNormativoEmbeddings
from buscador_rag_embeddings_variantes import (
    BuscadorEmbeddingsBalanceado,
    BuscadorEmbeddingsRecallAlto,
    BuscadorEmbeddingsRecallMaximo,
    BuscadorEmbeddingsRecallMedio,
)
from buscador_rag_general import BuscadorNormativoGeneral
from buscador_rag_hibrido import BuscadorNormativoHibrido
from buscador_rag_semantico import BuscadorNormativoSemantico


RAIZ = Path(__file__).parent


def cargar_holdout(ruta: Path) -> list[dict]:
    casos = []
    pregunta = None
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        coincidencia = re.match(r"^(\d+)\.\s+(.+)$", linea)
        if coincidencia:
            pregunta = coincidencia.group(2).strip()
            identificador = f"h{int(coincidencia.group(1)):03d}"
            continue
        if pregunta is not None and linea.strip().startswith(("Esperada:", "Esperadas:")):
            secciones = re.findall(r"NOR-[A-Z]{3}-\d+", linea)
            casos.append({"id": identificador, "consulta": pregunta, "secciones": secciones})
            pregunta = None
    if len(casos) != 60:
        raise ValueError(f"Se esperaban 60 preguntas de holdout y se cargaron {len(casos)}")
    return casos


def evaluar_holdout(buscador, casos: list[dict]) -> dict:
    recalls = []
    precisiones = []
    cantidades = []
    caracteres = []
    completas = 0
    por_tipo: dict[str, list[tuple[float, float, bool]]] = {}
    detalle = []

    for caso in casos:
        recuperados = buscador.recuperar(caso["consulta"], getattr(buscador, "k_entorno", 2))
        obtenidas = [item.seccion for item in recuperados]
        esperadas = caso["secciones"]
        aciertos = set(obtenidas) & set(esperadas)
        recall = len(aciertos) / len(esperadas)
        precision = len(aciertos) / len(obtenidas) if obtenidas else 0.0
        completa = recall == 1.0
        tipo = "dos_secciones" if len(esperadas) == 2 else "una_seccion"

        recalls.append(recall)
        precisiones.append(precision)
        cantidades.append(len(obtenidas))
        caracteres.append(sum(len(_normalizar(item.texto)) for item in recuperados))
        completas += completa
        por_tipo.setdefault(tipo, []).append((recall, precision, completa))
        detalle.append(
            {
                "id": caso["id"],
                "esperadas": esperadas,
                "obtenidas": obtenidas,
                "recall": recall,
                "precision": precision,
                "completa": completa,
            }
        )

    n = len(casos)
    return {
        "consultas": n,
        "recall_documentos": round(sum(recalls) / n, 3),
        "precision_documentos": round(sum(precisiones) / n, 3),
        "consultas_completas": completas,
        "chunks_por_consulta": round(sum(cantidades) / n, 2),
        "tokens_por_consulta": round(sum(caracteres) / n / 4),
        "por_tipo": {
            tipo: {
                "consultas": len(valores),
                "recall": round(sum(v[0] for v in valores) / len(valores), 3),
                "precision": round(sum(v[1] for v in valores) / len(valores), 3),
                "completas": sum(v[2] for v in valores),
            }
            for tipo, valores in sorted(por_tipo.items())
        },
        "errores": [item for item in detalle if not item["completa"]],
    }


def medir_latencia(buscador, consultas: list[str]) -> dict:
    if consultas:
        buscador.recuperar(consultas[0], getattr(buscador, "k_entorno", 2))
    tiempos = []
    for consulta in consultas:
        inicio = time.perf_counter()
        buscador.recuperar(consulta, getattr(buscador, "k_entorno", 2))
        tiempos.append((time.perf_counter() - inicio) * 1000)
    ordenados = sorted(tiempos)
    indice_p95 = min(len(ordenados) - 1, int(0.95 * len(ordenados)))
    return {
        "promedio_ms": round(statistics.mean(tiempos), 3),
        "mediana_ms": round(statistics.median(tiempos), 3),
        "p95_ms": round(ordenados[indice_p95], 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normas", type=Path, default=RAIZ / "normas" / "original")
    parser.add_argument("--consultas", type=Path, default=RAIZ / "rag" / "consultas_dev.jsonl")
    parser.add_argument(
        "--holdout",
        type=Path,
        default=RAIZ / "rag" / "preguntas_nuevas_holdout.txt",
    )
    parser.add_argument("--salida", type=Path)
    parser.add_argument(
        "--solo",
        action="append",
        choices=(
            "rag_actual",
            "rag_lexico_general",
            "rag_lexico_semantico",
            "rag_embeddings_lsa",
            "embeddings_balanceado",
            "embeddings_recall_medio",
            "embeddings_recall_alto",
            "embeddings_recall_maximo",
            "rag_hibrido_reranking",
        ),
        help="Evalúa solo uno o más modelos; puede repetirse.",
    )
    args = parser.parse_args()

    oficiales = cargar_dataset(args.consultas)
    holdout = cargar_holdout(args.holdout)
    consultas_latencia = [item["consulta"] for item in oficiales] + [item["consulta"] for item in holdout]
    clases = {
        "rag_actual": BuscadorNormativo,
        "rag_lexico_general": BuscadorNormativoGeneral,
        "rag_lexico_semantico": BuscadorNormativoSemantico,
        "rag_embeddings_lsa": BuscadorNormativoEmbeddings,
        "embeddings_balanceado": BuscadorEmbeddingsBalanceado,
        "embeddings_recall_medio": BuscadorEmbeddingsRecallMedio,
        "embeddings_recall_alto": BuscadorEmbeddingsRecallAlto,
        "embeddings_recall_maximo": BuscadorEmbeddingsRecallMaximo,
        "rag_hibrido_reranking": BuscadorNormativoHibrido,
    }
    if args.solo:
        clases = {nombre: clases[nombre] for nombre in args.solo}

    resultado = {
        "metodologia": {
            "oficial": "Métricas de evidencia del evaluador provisto por la cátedra.",
            "holdout": "Métricas de recuperación de documentos sobre 60 paráfrasis nuevas: 52 de una sección y 8 de dos.",
            "tokens": "Estimación oficial de 4 caracteres por token.",
            "entrenamiento_holdout": "Ningún índice usa las preguntas nuevas durante su construcción.",
        },
        "modelos": {},
    }

    for nombre, clase in clases.items():
        inicio = time.perf_counter()
        buscador = clase(args.normas)
        construccion_ms = (time.perf_counter() - inicio) * 1000
        resultado["modelos"][nombre] = {
            "construccion_ms": round(construccion_ms, 3),
            "latencia": medir_latencia(buscador, consultas_latencia),
            "oficial": {
                "entorno": evaluar_buscador(buscador, oficiales),
                "presupuesto": [
                    evaluar_recuperador(buscador.recuperar, oficiales, presupuesto)
                    for presupuesto in (256, 512, 1024)
                ],
            },
            "holdout": evaluar_holdout(buscador, holdout),
        }

    texto = json.dumps(resultado, ensure_ascii=False, indent=2) + "\n"
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(texto, encoding="utf-8")
    print(texto, end="")


if __name__ == "__main__":
    main()
