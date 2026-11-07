"""Agente de referencia con prompt configurable y modelo local de Transformers."""
import os
from pathlib import Path

from admision.ejemplo import _Partida, mensaje_de_sistema


class AgentePrompt:
    def __init__(self, modelo_lote, prompt, max_turnos=16, max_sin_json=3):
        self.modelo_lote, self.prompt = modelo_lote, prompt
        self.max_turnos, self.max_sin_json = max_turnos, max_sin_json

    def jugar_lote(self, entornos):
        partidas = [_Partida(e, self.max_turnos, self.max_sin_json) for e in entornos]
        for partida in partidas:
            partida.mensajes[0]["content"] = self.prompt
        while activas := [p for p in partidas if p.activa]:
            for partida, respuesta in zip(activas, self.modelo_lote([p.mensajes for p in activas]), strict=True):
                partida.recibir(respuesta)
        return [p.mensajes for p in partidas]


def leer_prompt():
    ruta = os.environ.get("TP_PROMPT")
    return Path(ruta).read_text(encoding="utf-8") if ruta else mensaje_de_sistema()


def construir_agente_local():
    ruta = os.environ.get("TP_MODELO_LOCAL")
    if not ruta or not Path(ruta).is_dir():
        raise RuntimeError("Definí TP_MODELO_LOCAL con la ruta al modelo descargado en Lightning.")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("Se requiere una GPU CUDA para esta línea de base.")
    tokenizer = AutoTokenizer.from_pretrained(ruta, local_files_only=True)
    modelo = AutoModelForCausalLM.from_pretrained(ruta, local_files_only=True, torch_dtype=torch.bfloat16).to("cuda")
    modelo.eval()

    def modelo_lote(conversaciones):
        respuestas = []
        # Una conversación a la vez limita la memoria; es la línea de base, no optimización de concurrencia.
        for conversacion in conversaciones:
            entradas = tokenizer.apply_chat_template(conversacion, tokenize=True, add_generation_prompt=True,
                                                      return_tensors="pt").to("cuda")
            with torch.inference_mode():
                salida = modelo.generate(entradas, max_new_tokens=384, do_sample=False,
                                         pad_token_id=tokenizer.eos_token_id)
            respuestas.append(tokenizer.decode(salida[0, entradas.shape[1]:], skip_special_tokens=True))
        return respuestas

    return AgentePrompt(modelo_lote, leer_prompt())
