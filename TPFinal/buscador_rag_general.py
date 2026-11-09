"""RAG léxico general, sin reglas que enruten frases a normas concretas.

Combina señales independientes del conjunto de preguntas:

- BM25 sobre las secciones completas;
- máximo BM25 de los apartados de cada sección;
- similitud TF-IDF de n-gramas de caracteres;
- coincidencia genérica con el título;
- selección de una segunda sección por cercanía y cobertura marginal.

El índice se construye exclusivamente a partir de ``ruta_normas``. Los
parámetros variables se incorporan mediante el fragmentador común del RAG
original, que lee ``parametros.yaml``.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from buscador_rag import (
    Fragmento,
    SeccionRecuperada,
    _fragmentar_normas,
    _sin_acentos,
    _tokens,
)


def _normalizar_puntajes(valores: dict[str, float]) -> dict[str, float]:
    maximo = max(valores.values(), default=0.0)
    if maximo <= 0:
        return {clave: 0.0 for clave in valores}
    return {clave: valor / maximo for clave, valor in valores.items()}


def _gramas_caracteres(texto: str, min_n: int = 3, max_n: int = 5) -> Counter[str]:
    """N-gramas dentro de cada palabra; toleran flexiones y errores leves."""
    resultado: Counter[str] = Counter()
    for palabra in _sin_acentos(texto).split():
        palabra = "".join(c for c in palabra if c.isalnum())
        if not palabra:
            continue
        acolchada = f"^{palabra}$"
        for n in range(min_n, max_n + 1):
            for inicio in range(max(0, len(acolchada) - n + 1)):
                resultado[acolchada[inicio : inicio + n]] += 1
    return resultado


class _BM25:
    def __init__(self, documentos: list[list[str]], k1: float = 1.4, b: float = 0.7):
        self.frecuencias = [Counter(documento) for documento in documentos]
        self.largos = [len(documento) for documento in documentos]
        self.largo_medio = sum(self.largos) / max(len(self.largos), 1)
        self.k1 = k1
        self.b = b
        df = Counter(token for documento in documentos for token in set(documento))
        n = len(documentos)
        self.idf = {
            token: math.log(1.0 + (n - frecuencia + 0.5) / (frecuencia + 0.5))
            for token, frecuencia in df.items()
        }

    def puntuar(self, consulta: list[str], indice: int) -> float:
        frecuencias = self.frecuencias[indice]
        largo = self.largos[indice]
        score = 0.0
        for token, frecuencia_consulta in Counter(consulta).items():
            tf = frecuencias.get(token, 0)
            if not tf:
                continue
            denominador = tf + self.k1 * (
                1 - self.b + self.b * largo / max(self.largo_medio, 1e-9)
            )
            score += (
                self.idf.get(token, 0.0)
                * tf
                * (self.k1 + 1)
                / denominador
                * min(frecuencia_consulta, 2)
            )
        return score


class _IndiceCaracteres:
    def __init__(self, textos: list[str]):
        self.documentos = [_gramas_caracteres(texto) for texto in textos]
        df = Counter(grama for documento in self.documentos for grama in documento)
        n = len(textos)
        self.idf = {
            grama: math.log(1.0 + n / (1.0 + frecuencia))
            for grama, frecuencia in df.items()
        }
        self.normas = [self._norma(documento) for documento in self.documentos]

    def _norma(self, vector: Counter[str]) -> float:
        return math.sqrt(
            sum((frecuencia * self.idf.get(grama, 0.0)) ** 2 for grama, frecuencia in vector.items())
        )

    def puntuar(self, consulta: str, indice: int) -> float:
        vector_consulta = _gramas_caracteres(consulta)
        norma_consulta = self._norma(vector_consulta)
        return self._puntuar_vector(vector_consulta, norma_consulta, indice)

    def _puntuar_vector(
        self,
        vector_consulta: Counter[str],
        norma_consulta: float,
        indice: int,
    ) -> float:
        norma_documento = self.normas[indice]
        if not norma_consulta or not norma_documento:
            return 0.0
        documento = self.documentos[indice]
        producto = sum(
            frecuencia
            * documento.get(grama, 0)
            * self.idf.get(grama, 0.0) ** 2
            for grama, frecuencia in vector_consulta.items()
        )
        return producto / (norma_consulta * norma_documento)

    def puntuar_todos(self, consulta: str) -> list[float]:
        """Calcula el vector de consulta una vez y lo compara con todo el índice."""
        vector_consulta = _gramas_caracteres(consulta)
        norma_consulta = self._norma(vector_consulta)
        return [
            self._puntuar_vector(vector_consulta, norma_consulta, indice)
            for indice in range(len(self.documentos))
        ]


class BuscadorNormativoGeneral:
    """Recuperador documental híbrido sin vocabulario específico de las consultas."""

    k_entorno = 2

    def __init__(self, ruta_normas: str | Path):
        self.fragmentos = _fragmentar_normas(Path(ruta_normas))
        agrupados: dict[str, list[Fragmento]] = defaultdict(list)
        for fragmento in self.fragmentos:
            agrupados[fragmento.seccion].append(fragmento)

        self.codigos = sorted(agrupados)
        self.fragmentos_por_seccion = {codigo: agrupados[codigo] for codigo in self.codigos}
        self.secciones = {
            codigo: self._armar_seccion(codigo, agrupados[codigo])
            for codigo in self.codigos
        }
        self._indice_seccion = {codigo: indice for indice, codigo in enumerate(self.codigos)}
        self._indices_fragmentos: dict[str, list[int]] = defaultdict(list)
        for indice, fragmento in enumerate(self.fragmentos):
            self._indices_fragmentos[fragmento.seccion].append(indice)

        textos_seccion = [self.secciones[codigo].texto for codigo in self.codigos]
        textos_fragmento = [fragmento.texto for fragmento in self.fragmentos]
        self._tokens_seccion = [_tokens(texto) for texto in textos_seccion]
        self._tokens_fragmento = [_tokens(texto) for texto in textos_fragmento]
        self._bm25_seccion = _BM25(self._tokens_seccion)
        self._bm25_fragmento = _BM25(self._tokens_fragmento)
        self._caracteres_seccion = _IndiceCaracteres(textos_seccion)
        self._caracteres_fragmento = _IndiceCaracteres(textos_fragmento)
        self._tokens_titulo = {
            codigo: set(_tokens(agrupados[codigo][0].titulo))
            for codigo in self.codigos
        }

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

    def _ranking_secciones(self, consulta: str) -> list[tuple[float, SeccionRecuperada]]:
        tokens_consulta = _tokens(consulta)
        conjunto_consulta = set(tokens_consulta)

        bm25_seccion = {
            codigo: self._bm25_seccion.puntuar(tokens_consulta, self._indice_seccion[codigo])
            for codigo in self.codigos
        }
        bm25_parrafo = {
            codigo: max(
                self._bm25_fragmento.puntuar(tokens_consulta, indice)
                for indice in self._indices_fragmentos[codigo]
            )
            for codigo in self.codigos
        }
        todos_caracteres_seccion = self._caracteres_seccion.puntuar_todos(consulta)
        todos_caracteres_fragmento = self._caracteres_fragmento.puntuar_todos(consulta)
        caracteres_seccion = {
            codigo: todos_caracteres_seccion[self._indice_seccion[codigo]]
            for codigo in self.codigos
        }
        caracteres_parrafo = {
            codigo: max(
                todos_caracteres_fragmento[indice]
                for indice in self._indices_fragmentos[codigo]
            )
            for codigo in self.codigos
        }
        titulo = {
            codigo: len(conjunto_consulta & self._tokens_titulo[codigo])
            / max(len(conjunto_consulta), 1)
            for codigo in self.codigos
        }

        señales = [
            (_normalizar_puntajes(bm25_seccion), 0.38),
            (_normalizar_puntajes(bm25_parrafo), 0.27),
            (_normalizar_puntajes(caracteres_seccion), 0.18),
            (_normalizar_puntajes(caracteres_parrafo), 0.12),
            (_normalizar_puntajes(titulo), 0.05),
        ]
        puntajes = {
            codigo: sum(valores[codigo] * peso for valores, peso in señales)
            for codigo in self.codigos
        }
        return sorted(
            ((puntajes[codigo], self.secciones[codigo]) for codigo in self.codigos),
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
        if relacion >= 0.78:
            return True

        tokens_consulta = set(_tokens(consulta))
        tokens_primero = set(self._tokens_seccion[self._indice_seccion[primero[1].seccion]])
        tokens_segundo = set(self._tokens_seccion[self._indice_seccion[segundo[1].seccion]])
        no_cubiertos = tokens_consulta - tokens_primero
        cobertura_marginal = len(no_cubiertos & tokens_segundo) / max(len(tokens_consulta), 1)
        return relacion >= 0.52 and cobertura_marginal >= 0.18

    def _ranking_fragmentos(self, consulta: str) -> list[tuple[float, Fragmento]]:
        tokens_consulta = _tokens(consulta)
        bm25 = {
            indice: self._bm25_fragmento.puntuar(tokens_consulta, indice)
            for indice in range(len(self.fragmentos))
        }
        caracteres = {
            indice: valor
            for indice, valor in enumerate(self._caracteres_fragmento.puntuar_todos(consulta))
        }
        bm25 = _normalizar_puntajes({str(k): v for k, v in bm25.items()})
        caracteres = _normalizar_puntajes({str(k): v for k, v in caracteres.items()})
        return sorted(
            (
                (0.72 * bm25[str(indice)] + 0.28 * caracteres[str(indice)], fragmento)
                for indice, fragmento in enumerate(self.fragmentos)
            ),
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


def construir_buscador(ruta_normas: str | Path) -> BuscadorNormativoGeneral:
    return BuscadorNormativoGeneral(ruta_normas)
