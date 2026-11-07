"""Divide por ID los 50 casos de práctica y sus fichas esperadas, sin usar sus resultados."""
import hashlib
import json
from pathlib import Path

SEMILLA = "prompt-v1-42"
BASE = Path("practica")
DESTINO = Path("experimentos/prompt/datos")


def leer(ruta):
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def escribir(ruta, registros):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in registros), encoding="utf-8")


def main():
    casos = leer(BASE / "casos.jsonl")
    ids = [c["id"] for c in casos]
    if len(ids) != 50 or len(set(ids)) != 50:
        raise ValueError("Se esperaban exactamente 50 IDs únicos de práctica")
    orden = sorted(ids, key=lambda i: hashlib.sha256(f"{SEMILLA}:{i}".encode()).hexdigest())
    particiones = {"desarrollo": set(orden[:30]), "validacion_reservada": set(orden[30:])}
    esperadas = {v: leer(BASE / f"esperadas-{v}.jsonl") for v in ("original", "b", "c")}
    for version, filas in esperadas.items():
        if len(filas) != len(ids) or {x["caso"] for x in filas} != set(ids):
            raise ValueError(f"Los IDs de esperadas-{version} no coinciden con los casos")
    for nombre, seleccion in particiones.items():
        escribir(DESTINO / nombre / "casos.jsonl", [c for c in casos if c["id"] in seleccion])
        for version, filas in esperadas.items():
            escribir(DESTINO / nombre / f"esperadas-{version}.jsonl", [e for e in filas if e["caso"] in seleccion])
    manifiesto = {"metodo": "orden sha256 de semilla:id; 30 desarrollo y 20 validación",
                  "semilla": SEMILLA, "ids": {k: sorted(v) for k, v in particiones.items()},
                  "nota": "La validación reservada no se usa para elegir o ajustar prompts."}
    (DESTINO / "particion.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Preparados 30 casos de desarrollo y 20 de validación reservada.")


if __name__ == "__main__":
    main()
