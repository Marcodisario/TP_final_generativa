import csv
import json
import unittest
from pathlib import Path

from admision.ejemplo import mensaje_de_sistema, primer_mensaje
from curado.convertir_trazas import convertir_traza, preparar, validar_traza

ROOT = Path(__file__).resolve().parents[1]


class ConversionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "historial/trazas.jsonl").open(encoding="utf-8") as archivo:
            cls.traza = json.loads(next(archivo))
        with (ROOT / "historial/historial.csv").open(encoding="utf-8-sig", newline="") as archivo:
            cls.fila = next(csv.DictReader(archivo))

    def test_formato_preserva_orden_argumentos_y_resultados(self):
        validar_traza(self.traza, self.fila)
        mensajes = convertir_traza(self.traza, mensaje_de_sistema())["messages"]
        self.assertEqual(mensajes[0], {"role": "system", "content": mensaje_de_sistema()})
        self.assertEqual(mensajes[1]["content"], primer_mensaje(self.traza["paciente_id"]))
        self.assertEqual(len(mensajes), 2 + 2 * len(self.traza["pasos"]) - 1)
        for i, paso in enumerate(self.traza["pasos"]):
            llamada = mensajes[2 + 2 * i]
            self.assertEqual(llamada["role"], "assistant")
            self.assertEqual(json.loads(llamada["content"]), {"herramienta": paso["herramienta"], "argumentos": paso["argumentos"]})
            if paso["herramienta"] != "registrar_decision":
                self.assertEqual(mensajes[3 + 2 * i], {"role": "user", "content": f"Resultado de {paso['herramienta']}:\n{paso['resultado']}"})
        self.assertEqual(mensajes[-1]["role"], "assistant")

    def test_rechaza_ficha_diferente(self):
        fila = dict(self.fila, registro="provisorio")
        with self.assertRaisesRegex(ValueError, "ficha distinta"):
            validar_traza(self.traza, fila)

    def test_usa_exactamente_las_filas_correctas(self):
        conversaciones, cantidades, _ = preparar(ROOT / "historial/historial.csv", ROOT / "historial_clasificado.csv", ROOT / "historial/trazas.jsonl")
        with (ROOT / "historial_clasificado.csv").open(encoding="utf-8-sig", newline="") as archivo:
            correctas = {f["id"] for f in csv.DictReader(archivo) if f["tipo"] == "correcta"}
        self.assertEqual(len(conversaciones), cantidades["correcta"])
        self.assertEqual({c["id"] for c in conversaciones}, correctas)
        self.assertEqual(len(conversaciones), len(correctas))


if __name__ == "__main__":
    unittest.main()
