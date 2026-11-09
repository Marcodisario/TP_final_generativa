"""Pruebas rápidas del contrato y de los parámetros dinámicos del RAG."""

from pathlib import Path
import unittest

from buscador_rag import construir_buscador


RAIZ = Path(__file__).parent


class BuscadorNormativoTest(unittest.TestCase):
    def test_cumple_contrato(self):
        buscador = construir_buscador(RAIZ / "normas" / "original")
        resultados = buscador.recuperar("paciente sin documento", 2)
        self.assertTrue(resultados)
        self.assertIsInstance(resultados[0].texto, str)

    def test_usa_parametros_de_la_carpeta_recibida(self):
        consulta = "¿Desde qué edad se pasa al box antes de registrar?"
        original = construir_buscador(RAIZ / "normas" / "original").recuperar(consulta, 2)[0].texto
        version_b = construir_buscador(RAIZ / "normas" / "b").recuperar(consulta, 2)[0].texto
        version_c = construir_buscador(RAIZ / "normas" / "c").recuperar(consulta, 2)[0].texto
        self.assertIn("P-ADM-2 = 67 años", original)
        self.assertIn("P-ADM-2 = 60 años", version_b)
        self.assertIn("P-ADM-2 = 72 años", version_c)

    def test_consulta_compuesta_recupera_dos_secciones(self):
        buscador = construir_buscador(RAIZ / "normas" / "c")
        resultados = buscador.recuperar("Llegó en ambulancia con dolor de pecho: ¿qué plazo tiene el ECG?", 2)
        secciones = {r.seccion for r in resultados}
        self.assertEqual({"NOR-TDE-01", "NOR-TDE-04"}, secciones)

    def test_entrega_usa_el_buscador_seleccionado(self):
        from entrega import construir_agente, construir_buscador as construir_desde_entrega

        buscador = construir_desde_entrega(RAIZ / "normas" / "original")
        self.assertEqual(3, buscador.k_entorno)
        self.assertTrue(callable(construir_agente))


if __name__ == "__main__":
    unittest.main()

