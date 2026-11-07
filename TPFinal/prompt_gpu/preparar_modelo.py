"""Descarga explícitamente una revisión pública del modelo para usarlo luego sin red."""
import json
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

MODELO = "Qwen/Qwen2.5-7B-Instruct"
REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python -m prompt_gpu.preparar_modelo /ruta/destino")
    destino = Path(sys.argv[1]).expanduser().resolve()
    if destino.exists() and any(destino.iterdir()):
        raise SystemExit("El destino no está vacío; elegí otra carpeta para no mezclar revisiones.")
    snapshot_download(repo_id=MODELO, revision=REVISION, local_dir=destino,
                      allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "LICENSE", "*.tiktoken"])
    (destino / "tp_modelo.json").write_text(json.dumps({"modelo": MODELO, "revision": REVISION}, indent=2) + "\n", encoding="utf-8")
    print(f"Modelo descargado en {destino}. La evaluación lo cargará sin red.")


if __name__ == "__main__":
    main()
