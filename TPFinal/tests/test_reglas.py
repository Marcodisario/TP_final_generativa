import unittest
from pathlib import Path

from curado.reglas import cobertura, circuitos, identidad_y_box, parametros

P = parametros(Path(__file__).resolve().parents[1] / "normas/original/parametros.yaml")


def estados(resultados):
    return {r.regla: r.estado for r in resultados}


class ReglasTest(unittest.TestCase):
    def test_pasaporte_urgente_es_provisorio(self):
        fila = dict(documento_tipo="pasaporte", documento_numero="ABC123", nivel="2", edad="30",
                    registro="provisorio", numero_documento="ABC123", box_antes_del_registro="sí")
        self.assertTrue(all(r.estado == "compatible" for r in identidad_y_box(fila, P)))
        fila["registro"] = "definitivo"
        self.assertEqual(estados(identidad_y_box(fila, P))["tipo_registro"], "violacion")

    def test_box_no_obligatorio_admite_ambas_opciones(self):
        fila = dict(documento_tipo="", documento_numero="", nivel="3", edad="30",
                    registro="provisorio", numero_documento="", box_antes_del_registro="sí")
        self.assertEqual(estados(identidad_y_box(fila, P))["box"], "compatible")
        fila["box_antes_del_registro"] = "no"
        self.assertEqual(estados(identidad_y_box(fila, P))["box"], "compatible")
        fila["edad"] = "67"
        self.assertEqual(estados(identidad_y_box(fila, P))["box"], "violacion")

    def test_sepsis_y_ambulancia(self):
        fila = dict(motivo="sospecha de sepsis", sospecha_sepsis="posible, sin signos de shock",
                    llegada="en ambulancia", circuito="codigo_sepsis", plazo_circuito_min="55")
        self.assertTrue(all(r.estado == "compatible" for r in circuitos(fila, P)))
        fila["plazo_circuito_min"] = "60"
        self.assertEqual(estados(circuitos(fila, P))["plazo"], "violacion")

    def test_numero_reservado_inactiva_notifica(self):
        fila = dict(lesion_trabajo="no", credenciales="Obra Social Tilcara (obra social) 30-966417-7",
                    entidad_verificada="Obra Social Tilcara", numero_verificado="30-966417-7",
                    respuesta_verificacion="inactiva", cobertura="sin_cobertura", entidad_a_notificar="Obra Social Tilcara")
        self.assertTrue(all(r.estado == "compatible" for r in cobertura(fila, P)))
        fila["entidad_a_notificar"] = ""
        self.assertEqual(estados(cobertura(fila, P))["notificacion"], "violacion")

    def test_art_prevalece_sobre_credencial(self):
        fila = dict(lesion_trabajo="trabajando", art_declarada="Andina ART CUIL 20-12345678-7",
                    credenciales="Prepaga Cumbre (prepaga) 123456/07", entidad_verificada="Andina ART",
                    numero_verificado="20-12345678-7", respuesta_verificacion="activa",
                    cobertura="art", entidad_a_notificar="Andina ART")
        self.assertTrue(all(r.estado == "compatible" for r in cobertura(fila, P)))

    def test_respuesta_de_entidad_equivocada_no_demuestra_afiliacion(self):
        fila = dict(lesion_trabajo="no", credenciales="Prepaga Cumbre (prepaga) 123456/02",
                    entidad_verificada="Prepaga Sierra", numero_verificado="123456/02",
                    respuesta_verificacion="activa", cobertura="prepaga", entidad_a_notificar="Prepaga Cumbre")
        e = estados(cobertura(fila, P))
        self.assertEqual(e["entidad_verificada"], "violacion")
        self.assertEqual(e["cobertura"], "insuficiente")
        self.assertEqual(e["notificacion"], "insuficiente")

    def test_datos_incompletos_no_son_error_automatico(self):
        fila = dict(lesion_trabajo="no", puede_responder="sí", acompanante="", cobertura_declarada="", credenciales="")
        self.assertTrue(all(r.estado == "insuficiente" for r in cobertura(fila, P)))

    def test_dos_credenciales_no_se_interpretan_como_una_entidad(self):
        fila = dict(lesion_trabajo="no", credenciales="Obra Social Fluvial (obra social) 25-448977-7; Prepaga Cumbre (prepaga) 967186/04",
                    entidad_verificada="Prepaga Cumbre", numero_verificado="967186/04", respuesta_verificacion="activa",
                    cobertura="prepaga", entidad_a_notificar="Prepaga Cumbre")
        self.assertTrue(all(r.estado == "insuficiente" for r in cobertura(fila, P)))


if __name__ == "__main__":
    unittest.main()
