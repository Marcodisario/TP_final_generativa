"""Pruebas de contrato para los RAG general y de embeddings LSA."""

from pathlib import Path
import unittest

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
CLASES = (
    BuscadorNormativoGeneral,
    BuscadorNormativoSemantico,
    BuscadorNormativoEmbeddings,
    BuscadorNormativoHibrido,
    BuscadorEmbeddingsBalanceado,
    BuscadorEmbeddingsRecallMedio,
    BuscadorEmbeddingsRecallAlto,
    BuscadorEmbeddingsRecallMaximo,
)


class DiccionarioSemanticoTest(unittest.TestCase):
    def test_no_contiene_rutas_a_normas(self):
        from buscador_rag_semantico import CONCEPTOS

        serializado = repr(CONCEPTOS)
        self.assertNotIn("NOR-", serializado)


class BuscadoresAlternativosTest(unittest.TestCase):
    def test_cumplen_contrato(self):
        for clase in CLASES:
            with self.subTest(clase=clase.__name__):
                buscador = clase(RAIZ / "normas" / "original")
                resultados = buscador.recuperar(
                    "paciente sin documento",
                    buscador.k_entorno,
                )
                self.assertTrue(resultados)
                self.assertTrue(all(isinstance(resultado.texto, str) for resultado in resultados))
                self.assertLessEqual(len(resultados), buscador.k_entorno)

    def test_parametros_salen_de_la_carpeta(self):
        consulta = "¿Desde qué edad se pasa al box antes de registrar?"
        for clase in CLASES:
            with self.subTest(clase=clase.__name__):
                original = clase(RAIZ / "normas" / "original").recuperar(consulta, 2)
                version_b = clase(RAIZ / "normas" / "b").recuperar(consulta, 2)
                version_c = clase(RAIZ / "normas" / "c").recuperar(consulta, 2)
                self.assertIn("P-ADM-2 = 67 años", "\n".join(r.texto for r in original))
                self.assertIn("P-ADM-2 = 60 años", "\n".join(r.texto for r in version_b))
                self.assertIn("P-ADM-2 = 72 años", "\n".join(r.texto for r in version_c))

    def test_consulta_vacia(self):
        for clase in CLASES:
            with self.subTest(clase=clase.__name__):
                buscador = clase(RAIZ / "normas" / "original")
                self.assertEqual([], buscador.recuperar("", 2))
                self.assertEqual([], buscador.recuperar("consulta", 0))


if __name__ == "__main__":
    unittest.main()
