import json
import unittest

from prompt_gpu.agente import AgentePrompt
from prompt_gpu.preparar_casos import BASE, SEMILLA, leer


class EntornoFalso:
    paciente_id = "P-0001"

    def __init__(self):
        self.llamadas = []

    def paso(self, herramienta, argumentos):
        self.llamadas.append((herramienta, argumentos))
        return ("ok", herramienta == "registrar_decision")


class PruebasPrompt(unittest.TestCase):
    def test_agente_usa_prompt_y_conserva_conversacion(self):
        respuestas = iter([json.dumps({"herramienta": "leer_triage", "argumentos": {"paciente_id": "P-0001"}}),
                           json.dumps({"herramienta": "registrar_decision", "argumentos": {}})])
        agente = AgentePrompt(lambda conversaciones: [next(respuestas) for _ in conversaciones], "PROMPT DE PRUEBA")
        entorno = EntornoFalso()
        mensajes = agente.jugar_lote([entorno])[0]
        self.assertEqual(mensajes[0]["content"], "PROMPT DE PRUEBA")
        self.assertEqual([x["role"] for x in mensajes], ["system", "user", "assistant", "user", "assistant"])
        self.assertEqual(mensajes[3]["content"], "Resultado de leer_triage:\nok")
        self.assertEqual(len(entorno.llamadas), 2)

    def test_particion_estable_y_sin_solapamiento(self):
        import hashlib
        ids = [x["id"] for x in leer(BASE / "casos.jsonl")]
        orden = sorted(ids, key=lambda i: hashlib.sha256(f"{SEMILLA}:{i}".encode()).hexdigest())
        self.assertEqual(len(ids), 50)
        self.assertEqual(len(set(orden[:30]) & set(orden[30:])), 0)
        self.assertEqual(len(set(orden)), 50)


if __name__ == "__main__":
    unittest.main()
