"""Corre una línea de base de prompt, conservando configuración, prompt y evaluación."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

from prompt_gpu.agente import leer_prompt


def sha(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nombre", required=True, help="Nombre nuevo de la corrida; no se sobrescribe")
    parser.add_argument("--normas", choices=("original", "b", "c"), default="original")
    args = parser.parse_args()
    if not args.nombre.replace("-", "").replace("_", "").isalnum():
        parser.error("El nombre solo admite letras, números, guiones y guiones bajos")
    modelo = Path(os.environ.get("TP_MODELO_LOCAL", ""))
    manifiesto = modelo / "tp_modelo.json"
    if not manifiesto.is_file():
        parser.error("Falta TP_MODELO_LOCAL o tp_modelo.json; descargá primero la revisión fijada.")
    import torch
    from transformers import AutoTokenizer
    if not torch.cuda.is_available():
        parser.error("Se requiere GPU CUDA para medir esta línea de base.")
    gpu = torch.cuda.get_device_name(0)
    memoria = torch.cuda.get_device_properties(0).total_memory
    if "A100" not in gpu.upper() or not (35 * 1024**3 <= memoria < 50 * 1024**3):
        parser.error(f"La misión requiere A100 de 40 GB; se detectó {gpu} con {memoria / 1024**3:.1f} GiB.")
    ruta_base = Path("experimentos/prompt/datos/desarrollo")
    casos, esperadas = ruta_base / "casos.jsonl", ruta_base / f"esperadas-{args.normas}.jsonl"
    if not casos.is_file() or not esperadas.is_file():
        parser.error("Primero ejecutá python -m prompt_gpu.preparar_casos.")
    salida = Path("experimentos/prompt/corridas") / args.nombre
    salida.mkdir(parents=True, exist_ok=False)
    prompt = leer_prompt()
    prompt_archivo = salida / "prompt.txt"
    prompt_archivo.write_text(prompt, encoding="utf-8")
    tokenizer = AutoTokenizer.from_pretrained(modelo, local_files_only=True)
    comando = [sys.executable, "-m", "admision.correr", "practica", "--entrega", "entrega.py",
               "--casos", str(casos), "--esperadas", str(esperadas), "--normas", f"normas/{args.normas}",
               "--salida", str(salida)]
    config = {"modelo": json.loads(manifiesto.read_text(encoding="utf-8")), "hardware": gpu,
              "vram_bytes": memoria,
              "versiones": {x: importlib.metadata.version(x) for x in ("torch", "transformers", "huggingface-hub", "accelerate")},
              "generacion": {"do_sample": False, "max_new_tokens": 384, "dtype": "bfloat16", "secuencial": True},
              "prompt_tokens_sin_tokens_especiales": len(tokenizer.encode(prompt, add_special_tokens=False)),
              "prompt_sha256": sha(prompt_archivo), "casos_sha256": sha(casos), "esperadas_sha256": sha(esperadas),
              "archivos_normas_sha256": {p.name: sha(p) for p in sorted(Path(f"normas/{args.normas}").glob("*")) if p.is_file()},
              "codigo_sha256": {str(p): sha(p) for p in (Path("entrega.py"), Path("buscador_rag.py"), Path("prompt_gpu/agente.py"), Path("prompt_gpu/medir_prompt.py"), Path("prompt_gpu/uv.lock"))},
              "comando": comando, "normas": args.normas, "conjunto": "desarrollo"}
    (salida / "configuracion.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    env = os.environ.copy()
    env["TP_PROMPT"] = str(prompt_archivo.resolve())
    proceso = subprocess.run(comando, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True)
    (salida / "salida.txt").write_text(proceso.stdout + "\n" + proceso.stderr, encoding="utf-8")
    print(proceso.stdout, proceso.stderr)
    if proceso.returncode:
        raise SystemExit(proceso.returncode)
    resumen = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
    if resumen.get("error"):
        raise SystemExit(f"La corrida del agente falló: {resumen['error']}; ver {salida}")
    print(f"Corrida guardada en {salida}; prompt: {config['prompt_tokens_sin_tokens_especiales']} tokens.")


if __name__ == "__main__":
    main()
