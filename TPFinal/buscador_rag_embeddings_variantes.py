"""Cuatro niveles de recall para el mismo recuperador de embeddings.

Las políticas son generales y se definieron sin calibrarlas con las preguntas
de evaluación. Solo cambia cuántas normas del mismo ranking se entregan.
"""

from __future__ import annotations

from pathlib import Path

from buscador_rag import SeccionRecuperada
from buscador_rag_embeddings import BuscadorNormativoEmbeddings


class BuscadorEmbeddingsBalanceado(BuscadorNormativoEmbeddings):
    """Devuelve una norma; agrega la segunda si queda a menos de 20 %."""

    k_entorno = 2

    def _cantidad_documentos(
        self,
        ranking: list[tuple[float, SeccionRecuperada]],
        maximo: int,
    ) -> int:
        if not ranking or maximo <= 0:
            return 0
        if maximo == 1 or len(ranking) == 1 or ranking[0][0] <= 0:
            return 1
        relacion = ranking[1][0] / ranking[0][0]
        return 2 if relacion >= 0.80 else 1


class BuscadorEmbeddingsRecallMedio(BuscadorNormativoEmbeddings):
    """Devuelve siempre las dos normas mejor posicionadas."""

    k_entorno = 2

    def _cantidad_documentos(
        self,
        ranking: list[tuple[float, SeccionRecuperada]],
        maximo: int,
    ) -> int:
        return min(2, maximo, len(ranking))


class BuscadorEmbeddingsRecallAlto(BuscadorNormativoEmbeddings):
    """Devuelve dos normas; agrega la tercera si queda a menos de 10 %."""

    k_entorno = 3

    def _cantidad_documentos(
        self,
        ranking: list[tuple[float, SeccionRecuperada]],
        maximo: int,
    ) -> int:
        limite = min(maximo, len(ranking))
        if limite < 3 or ranking[0][0] <= 0:
            return min(2, limite)
        relacion = ranking[2][0] / ranking[0][0]
        return 3 if relacion >= 0.90 else 2


class BuscadorEmbeddingsRecallMaximo(BuscadorNormativoEmbeddings):
    """Devuelve siempre las tres normas mejor posicionadas."""


def construir_buscador_balanceado(ruta_normas: str | Path) -> BuscadorEmbeddingsBalanceado:
    return BuscadorEmbeddingsBalanceado(ruta_normas)


def construir_buscador_recall_medio(ruta_normas: str | Path) -> BuscadorEmbeddingsRecallMedio:
    return BuscadorEmbeddingsRecallMedio(ruta_normas)


def construir_buscador_recall_alto(ruta_normas: str | Path) -> BuscadorEmbeddingsRecallAlto:
    return BuscadorEmbeddingsRecallAlto(ruta_normas)


def construir_buscador_recall_maximo(ruta_normas: str | Path) -> BuscadorEmbeddingsRecallMaximo:
    return BuscadorEmbeddingsRecallMaximo(ruta_normas)
