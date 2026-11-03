import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from curado.clasificar import clasificar_fila
from curado.reglas import parametros

ROOT = Path(__file__).resolve().parents[1]
P = parametros(ROOT / "normas/original/parametros.yaml")
with (ROOT / "historial/historial.csv").open(encoding="utf-8-sig", newline="") as archivo:
    FILAS = {f["id"]: f for f in csv.DictReader(archivo)}


class ClasificacionTest(unittest.TestCase):
    def test_error_tiene_prioridad_sobre_desviacion_de_costumbre(self):
        fila = dict(FILAS["H-0014"], aviso_al_voluntariado="sí")
        resultado = clasificar_fila(fila, P)
        self.assertEqual(resultado["tipo"], "error")
        self.assertIn("voluntariado_difiere_costumbre", resultado["motivos_ruido"])
        self.assertIn("tipo_registro", [v["regla"] for v in resultado["violaciones"]])

    def test_dos_credenciales_y_decision_no_habitual(self):
        resultado = clasificar_fila(FILAS["H-0334"], P)
        self.assertEqual(resultado["tipo"], "ruido")
        self.assertIn("eligio_obra_social_con_prepaga", resultado["motivos_ruido"])
        self.assertFalse(resultado["revisar"])

    def test_dos_credenciales_tambien_verifica_normas_de_la_elegida(self):
        fila = dict(FILAS["H-0011"])
        fila["numero_verificado"] = "numero-distinto"
        resultado = clasificar_fila(fila, P)
        self.assertEqual(resultado["tipo"], "error")
        self.assertIn("numero_verificado", [v["regla"] for v in resultado["violaciones"]])

    def test_entidad_no_identificada_queda_pendiente(self):
        fila = dict(FILAS["H-0011"], entidad_verificada="Entidad desconocida")
        self.assertTrue(clasificar_fila(fila, P)["revisar"])

    def test_no_usar_operador_como_regla(self):
        fila = dict(FILAS["H-0001"], operador="OP-11")
        self.assertEqual(clasificar_fila(fila, P)["tipo"], clasificar_fila(FILAS["H-0001"], P)["tipo"])

    def test_pendiente_no_sobrescribe_clasificacion(self):
        carpeta_temporal = ROOT / "resultados"
        carpeta_temporal.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=carpeta_temporal) as carpeta:
            carpeta = Path(carpeta)
            origen, salida = carpeta / "entrada.csv", carpeta / "salida.csv"
            fila = dict(FILAS["H-0011"], entidad_verificada="Entidad desconocida")
            with origen.open("w", encoding="utf-8", newline="") as archivo:
                escritor = csv.DictWriter(archivo, fieldnames=fila.keys())
                escritor.writeheader()
                escritor.writerow(fila)
            salida.write_text("conservar\n", encoding="utf-8")
            comando = [sys.executable, "-m", "curado.clasificar", "--historial", str(origen),
                       "--salida", str(salida), "--trazas", str(carpeta / "trazas.jsonl"),
                       "--resumen", str(carpeta / "resumen.json")]
            resultado = subprocess.run(comando, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(resultado.returncode, 0)
            self.assertEqual(salida.read_text(encoding="utf-8"), "conservar\n")
            self.assertIn('"revisar": true', (carpeta / "trazas.jsonl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
