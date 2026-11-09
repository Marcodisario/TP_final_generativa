"""RAG híbrido con generación multicanal de candidatos y reranking.

Primera etapa:
- recuperador léxico BM25/n-gramas;
- recuperador léxico-semántico por conceptos;
- recuperador de embeddings densos LSA.

Segunda etapa:
- Reciprocal Rank Fusion;
- reranking por señales normalizadas, cobertura léxica y conceptual,
  coincidencias de frases, título y mejor apartado;
- selección genérica de un segundo documento mediante ganancia marginal,
  segmentación y referencias explícitas del corpus.

No contiene rutas de frases a códigos ``NOR-*`` y no ajusta pesos con las
preguntas del holdout.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from buscador_rag import Fragmento, SeccionRecuperada, _tokens
from buscador_rag_embeddings import BuscadorNormativoEmbeddings
from buscador_rag_general import BuscadorNormativoGeneral, _normalizar_puntajes
from buscador_rag_semantico import (
    BuscadorNormativoSemantico,
    _marcadores_conceptuales,
)


def _normalizar_ranking(
    ranking: list[tuple[float, SeccionRecuperada]],
) -> dict[str, float]:
    valores = {documento.seccion: max(score, 0.0) for score, documento in ranking}
    return _normalizar_puntajes(valores)


def _rrf_rankings(
    rankings: list[list[tuple[float, SeccionRecuperada]]],
    constante: int = 12,
) -> dict[str, float]:
    fusion: defaultdict[str, float] = defaultdict(float)
    for ranking in rankings:
        for posicion, (_, documento) in enumerate(ranking, start=1):
            fusion[documento.seccion] += 1.0 / (constante + posicion)
    return dict(fusion)


class BuscadorNormativoHibrido:
    """Recuperador híbrido documental con reranker no supervisado."""

    k_entorno = 2

    def __init__(self, ruta_normas: str | Path):
        ruta = Path(ruta_normas)
        self.general = BuscadorNormativoGeneral(ruta)
        self.semantico = BuscadorNormativoSemantico(ruta)
        self.embeddings = BuscadorNormativoEmbeddings(ruta)
        self.codigos = self.semantico.codigos
        self.secciones = self.semantico.secciones
        self.fragmentos = self.semantico.fragmentos
        self._tokens_documento = {
            codigo: set(_tokens(documento.texto))
            for codigo, documento in self.secciones.items()
        }
        self._tokens_titulo = {
            codigo: set(_tokens(documento.texto.partition("\n")[0]))
            for codigo, documento in self.secciones.items()
        }
        self._conceptos_documento = {
            codigo: _marcadores_conceptuales(documento.texto)
            for codigo, documento in self.secciones.items()
        }

    @staticmethod
    def _coincidencia_frases(consulta: str, documento: str) -> float:
        consulta_tokens = _tokens(consulta)
        documento_tokens = _tokens(documento)
        bigramas_documento = set(zip(documento_tokens, documento_tokens[1:]))
        trigramas_documento = set(zip(documento_tokens, documento_tokens[1:], documento_tokens[2:]))
        bigramas_consulta = list(zip(consulta_tokens, consulta_tokens[1:]))
        trigramas_consulta = list(zip(consulta_tokens, consulta_tokens[1:], consulta_tokens[2:]))
        coincidencias = sum(frase in bigramas_documento for frase in bigramas_consulta)
        coincidencias += 2 * sum(frase in trigramas_documento for frase in trigramas_consulta)
        denominador = max(len(bigramas_consulta) + 2 * len(trigramas_consulta), 1)
        return coincidencias / denominador

    def _ranking_secciones(self, consulta: str) -> list[tuple[float, SeccionRecuperada]]:
        rankings = [
            self.general._ranking_secciones(consulta),
            self.semantico._ranking_secciones(consulta),
            self.embeddings._ranking_secciones(consulta),
        ]
        puntajes_general = _normalizar_ranking(rankings[0])
        puntajes_semantico = _normalizar_ranking(rankings[1])
        puntajes_embeddings = _normalizar_ranking(rankings[2])
        rrf = _normalizar_puntajes(_rrf_rankings(rankings))

        candidatos = set()
        for ranking in rankings:
            candidatos.update(documento.seccion for _, documento in ranking[:8])

        tokens_consulta = set(_tokens(consulta))
        conceptos_consulta = _marcadores_conceptuales(consulta)
        cobertura_lexica = {
            codigo: len(tokens_consulta & self._tokens_documento[codigo]) / max(len(tokens_consulta), 1)
            for codigo in candidatos
        }
        cobertura_conceptual = {
            codigo: len(conceptos_consulta & self._conceptos_documento[codigo]) / max(len(conceptos_consulta), 1)
            for codigo in candidatos
        }
        titulo = {
            codigo: len(tokens_consulta & self._tokens_titulo[codigo]) / max(len(tokens_consulta), 1)
            for codigo in candidatos
        }
        frases = {
            codigo: self._coincidencia_frases(consulta, self.secciones[codigo].texto)
            for codigo in candidatos
        }
        cobertura_lexica = _normalizar_puntajes(cobertura_lexica)
        cobertura_conceptual = _normalizar_puntajes(cobertura_conceptual)
        titulo = _normalizar_puntajes(titulo)
        frases = _normalizar_puntajes(frases)

        # Reranker: todos los pesos son globales y se aplican igual a cada norma.
        puntajes = {
            codigo: (
                0.21 * puntajes_general.get(codigo, 0.0)
                + 0.25 * puntajes_semantico.get(codigo, 0.0)
                + 0.22 * puntajes_embeddings.get(codigo, 0.0)
                + 0.16 * rrf.get(codigo, 0.0)
                + 0.06 * cobertura_lexica.get(codigo, 0.0)
                + 0.06 * cobertura_conceptual.get(codigo, 0.0)
                + 0.02 * titulo.get(codigo, 0.0)
                + 0.02 * frases.get(codigo, 0.0)
            )
            for codigo in candidatos
        }
        return sorted(
            ((score, self.secciones[codigo]) for codigo, score in puntajes.items()),
            key=lambda par: (-par[0], par[1].seccion),
        )

    def _necesita_segunda(
        self,
        consulta: str,
        ranking: list[tuple[float, SeccionRecuperada]],
    ) -> bool:
        if len(ranking) < 2 or ranking[0][0] <= 0:
            return False
        primero, segundo = ranking[0], ranking[1]
        relacion = segundo[0] / primero[0]
        if relacion >= 0.86:
            return True

        conceptos = _marcadores_conceptuales(consulta)
        pendientes = conceptos - self._conceptos_documento[primero[1].seccion]
        ganancia = len(pendientes & self._conceptos_documento[segundo[1].seccion]) / max(len(conceptos), 1)
        if relacion >= 0.52 and ganancia >= 0.18:
            return True

        ganadores_segmentos = []
        for segmento in self.semantico._segmentos(consulta):
            ranking_segmento = self._ranking_secciones_sin_segmentar(segmento)
            if ranking_segmento and ranking_segmento[0][0] >= 0.42:
                ganadores_segmentos.append(ranking_segmento[0][1].seccion)
        if primero[1].seccion in ganadores_segmentos and segundo[1].seccion in ganadores_segmentos:
            return relacion >= 0.45

        relacionados = self.semantico._referencias[primero[1].seccion] | {
            codigo
            for codigo, referencias in self.semantico._referencias.items()
            if primero[1].seccion in referencias
        }
        return segundo[1].seccion in relacionados and relacion >= 0.58

    def _ranking_secciones_sin_segmentar(
        self,
        consulta: str,
    ) -> list[tuple[float, SeccionRecuperada]]:
        """Mismo reranking; método separado para evitar recursión de selección."""
        return self._ranking_secciones(consulta)

    @staticmethod
    def _ranking_a_mapa_fragmentos(
        ranking: list[tuple[float, Fragmento]],
    ) -> tuple[dict[tuple[str, int], float], dict[tuple[str, int], int]]:
        scores = {(fragmento.seccion, fragmento.orden): max(score, 0.0) for score, fragmento in ranking}
        scores = _normalizar_puntajes({f"{k[0]}:{k[1]}": v for k, v in scores.items()})
        mapa_scores = {}
        posiciones = {}
        for posicion, (_, fragmento) in enumerate(ranking, start=1):
            clave = (fragmento.seccion, fragmento.orden)
            mapa_scores[clave] = scores[f"{clave[0]}:{clave[1]}"]
            posiciones[clave] = posicion
        return mapa_scores, posiciones

    def _ranking_fragmentos(self, consulta: str) -> list[tuple[float, Fragmento]]:
        rankings = [
            self.general._ranking_fragmentos(consulta),
            self.semantico._ranking_fragmentos(consulta),
            self.embeddings._ranking_fragmentos(consulta),
        ]
        mapas = [self._ranking_a_mapa_fragmentos(ranking) for ranking in rankings]
        fragmentos = {
            (fragmento.seccion, fragmento.orden): fragmento
            for fragmento in self.fragmentos
        }
        puntajes = {}
        for clave in fragmentos:
            scores = [mapa[0].get(clave, 0.0) for mapa in mapas]
            rrf = sum(1.0 / (12 + mapa[1].get(clave, 999)) for mapa in mapas)
            puntajes[clave] = 0.26 * scores[0] + 0.32 * scores[1] + 0.26 * scores[2] + 0.16 * rrf
        return sorted(
            ((score, fragmentos[clave]) for clave, score in puntajes.items()),
            key=lambda par: (-par[0], par[1].seccion, par[1].orden),
        )

    def recuperar(self, consulta: str, k: int) -> list[SeccionRecuperada | Fragmento]:
        if not isinstance(consulta, str) or not consulta.strip() or k <= 0:
            return []
        if k <= self.k_entorno:
            ranking = self._ranking_secciones(consulta)
            limite = 2 if self._necesita_segunda(consulta, ranking) else 1
            return [documento for _, documento in ranking[: min(k, limite)]]
        return [fragmento for _, fragmento in self._ranking_fragmentos(consulta)[:k]]


def construir_buscador(ruta_normas: str | Path) -> BuscadorNormativoHibrido:
    return BuscadorNormativoHibrido(ruta_normas)
