"""RAG único de embeddings conceptuales locales.

No combina otros recuperadores ni tiene una etapa de reranking. Construye un
solo espacio vectorial LSA a partir de las normas, sus apartados, títulos y un
glosario general de conceptos. Cada norma queda representada por un vector
estático y las consultas se ordenan directamente por similitud coseno.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.preprocessing import Normalizer

from buscador_rag import Fragmento, SeccionRecuperada, _fragmentar_normas, _sin_acentos, _tokens
from buscador_rag_semantico import CONCEPTOS, _texto_semantico


class BuscadorNormativoEmbeddings:
    """Recuperador documental de una sola etapa por similitud de embeddings."""

    # Política seleccionada: devuelve dos normas y suma una tercera solo si su
    # similitud queda cerca de la primera, para priorizar recall sin usar
    # siempre el máximo de contexto.
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
        self._indices_fragmentos: dict[str, list[int]] = defaultdict(list)
        for indice, fragmento in enumerate(self.fragmentos):
            self._indices_fragmentos[fragmento.seccion].append(indice)

        textos_seccion = [self._preparar(self.secciones[codigo].texto) for codigo in self.codigos]
        textos_fragmento = [self._preparar(fragmento.texto) for fragmento in self.fragmentos]
        textos_titulo = [self._preparar(agrupados[codigo][0].titulo) for codigo in self.codigos]
        textos_glosario = [
            self._preparar(
                f"cx{concepto.replace('_', '')} "
                + " ".join(expresiones)
                + " "
                + " ".join(expresiones)
            )
            for concepto, expresiones in CONCEPTOS.items()
        ]
        corpus = textos_seccion + textos_fragmento + textos_titulo + textos_glosario

        # Una única transformación de texto a embedding denso. Palabras y
        # caracteres forman la entrada del mismo modelo LSA.
        self._vectorizador = FeatureUnion(
            [
                (
                    "palabras",
                    TfidfVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 3),
                        min_df=1,
                        sublinear_tf=True,
                        norm=None,
                    ),
                ),
                (
                    "caracteres",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(3, 5),
                        min_df=1,
                        sublinear_tf=True,
                        max_features=40000,
                        norm=None,
                    ),
                ),
            ],
            transformer_weights={"palabras": 1.0, "caracteres": 0.45},
        )
        matriz_tfidf = self._vectorizador.fit_transform(corpus)
        componentes = max(2, min(96, matriz_tfidf.shape[0] - 1, matriz_tfidf.shape[1] - 1))
        self._svd = TruncatedSVD(n_components=componentes, n_iter=12, random_state=42)
        self._normalizador = Normalizer(copy=False)
        matriz = self._normalizador.fit_transform(self._svd.fit_transform(matriz_tfidf))

        n_secciones = len(self.codigos)
        n_fragmentos = len(self.fragmentos)
        vectores_seccion = matriz[:n_secciones]
        self._vectores_fragmento = matriz[n_secciones : n_secciones + n_fragmentos]
        inicio_titulos = n_secciones + n_fragmentos
        vectores_titulo = matriz[inicio_titulos : inicio_titulos + n_secciones]

        # Un vector estático por documento. Su composición no depende de la
        # consulta y evita diluir apartados útiles en secciones largas.
        vectores_documento = []
        for indice, codigo in enumerate(self.codigos):
            indices = self._indices_fragmentos[codigo]
            centroide_fragmentos = np.mean(self._vectores_fragmento[indices], axis=0)
            vector = 0.55 * vectores_seccion[indice] + 0.30 * centroide_fragmentos + 0.15 * vectores_titulo[indice]
            norma = np.linalg.norm(vector)
            vectores_documento.append(vector / norma if norma else vector)
        self._vectores_documento = np.asarray(vectores_documento)

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

    @staticmethod
    def _preparar(texto: str) -> str:
        semantico = _texto_semantico(texto)
        primera, _, resto = semantico.partition("\n")
        return f"{primera} {primera} {resto}"

    def _vector(self, texto: str) -> np.ndarray:
        tfidf = self._vectorizador.transform([self._preparar(texto)])
        vector = self._svd.transform(tfidf)
        return self._normalizador.transform(vector)[0]

    @staticmethod
    def _segmentos(consulta: str) -> list[str]:
        partes = re.split(r"[;:.?]|\b(?:y|pero|aunque|ademas|con)\b", _sin_acentos(consulta))
        return [parte.strip() for parte in partes if len(_tokens(parte)) >= 2]

    def _similitudes(self, consulta: str) -> tuple[np.ndarray, list[np.ndarray]]:
        vector_completo = self._vector(consulta)
        similitud_completa = np.maximum(self._vectores_documento @ vector_completo, 0.0)
        similitudes_segmentos = [
            np.maximum(self._vectores_documento @ self._vector(segmento), 0.0)
            for segmento in self._segmentos(consulta)
        ]
        if similitudes_segmentos:
            maximo_segmentos = np.max(np.vstack(similitudes_segmentos), axis=0)
            similitud_final = 0.76 * similitud_completa + 0.24 * maximo_segmentos
        else:
            similitud_final = similitud_completa
        return similitud_final, similitudes_segmentos

    def _ranking_secciones(self, consulta: str) -> list[tuple[float, SeccionRecuperada]]:
        similitudes, _ = self._similitudes(consulta)
        return sorted(
            (
                (float(similitudes[indice]), self.secciones[codigo])
                for indice, codigo in enumerate(self.codigos)
            ),
            key=lambda par: (-par[0], par[1].seccion),
        )

    def _ranking_fragmentos(self, consulta: str) -> list[tuple[float, Fragmento]]:
        vector = self._vector(consulta)
        similitudes = np.maximum(self._vectores_fragmento @ vector, 0.0)
        return sorted(
            ((float(similitudes[i]), fragmento) for i, fragmento in enumerate(self.fragmentos)),
            key=lambda par: (-par[0], par[1].seccion, par[1].orden),
        )

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

    def recuperar(self, consulta: str, k: int) -> list[SeccionRecuperada | Fragmento]:
        if not isinstance(consulta, str) or not consulta.strip() or k <= 0:
            return []
        if k <= self.k_entorno:
            ranking = self._ranking_secciones(consulta)
            limite = self._cantidad_documentos(ranking, k)
            return [documento for _, documento in ranking[:limite]]
        return [fragmento for _, fragmento in self._ranking_fragmentos(consulta)[:k]]


def construir_buscador(ruta_normas: str | Path) -> BuscadorNormativoEmbeddings:
    return BuscadorNormativoEmbeddings(ruta_normas)
