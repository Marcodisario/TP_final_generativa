"""Exploración reproducible de patrones no regulados en el historial."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from curado.reglas import evaluar_fila, normalizar, parametros


def resumir(grupos):
    return {clave: {"total": len(filas), "si": sum(f["aviso_al_voluntariado"] == "sí" for f in filas),
                    "no": sum(f["aviso_al_voluntariado"] == "no" for f in filas)}
            for clave, filas in sorted(grupos.items())}


def explorar(filas, p):
    sin_error = [f for f in filas if not any(r.estado == "violacion" for r in evaluar_fila(f, p))]
    salidas = {}
    for etiqueta, grupo in (("todas", filas), ("sin_alerta_normativa", sin_error)):
        variables = {"edad": lambda f: str(int(f["edad"]) // 10 * 10),
                     "nivel": lambda f: f["nivel"], "llegada": lambda f: f["llegada"],
                     "puede_responder": lambda f: f["puede_responder"],
                     "acompanante": lambda f: "sí" if f["acompanante"] else "no",
                     "lesion_trabajo": lambda f: f["lesion_trabajo"], "motivo": lambda f: f["motivo"],
                     "cobertura_registrada": lambda f: f["cobertura"], "operador": lambda f: f["operador"]}
        estadisticas = {}
        for nombre, funcion in variables.items():
            grupos = defaultdict(list)
            for fila in grupo:
                grupos[funcion(fila)].append(fila)
            estadisticas[nombre] = resumir(grupos)
        dobles = [f for f in grupo if ";" in f["credenciales"] and normalizar(f["lesion_trabajo"]) == "no"]
        eleccion = Counter("prepaga" if f["entidad_verificada"].startswith("Prepaga ") else
                           "obra_social" if f["entidad_verificada"].startswith("Obra Social ") else "otra_o_sin_verificar" for f in dobles)
        salidas[etiqueta] = {"filas": len(grupo), "voluntariado": estadisticas,
                             "dos_credenciales": {"total": len(dobles), "verificada": dict(eleccion)}}
    return salidas


def evidencias(filas, p):
    """Se conservan IDs a favor y en contra; las hipótesis no son etiquetas finales."""
    limpios = {f["id"] for f in filas if not any(r.estado == "violacion" for r in evaluar_fila(f, p))}
    voluntariado = {"a_favor": [], "excepciones": []}
    dos = {"a_favor": [], "excepciones": [], "ambiguas": []}
    box = {"a_favor": [], "excepciones": [], "ambiguas": []}
    for f in filas:
        esperado = int(f["edad"]) >= 75 and not f["acompanante"]
        observado = normalizar(f["aviso_al_voluntariado"])
        item = {"id": f["id"], "operador": f["operador"], "sin_alerta_normativa": f["id"] in limpios,
                "edad": int(f["edad"]), "tiene_acompanante": bool(f["acompanante"]),
                "aviso": observado}
        voluntariado["a_favor" if (observado == "si") == esperado else "excepciones"].append(item)
        if int(f["edad"]) < p["P-ADM-2"] and int(f["nivel"]) > p["P-ADM-1"]:
            valor_box = normalizar(f["box_antes_del_registro"])
            categoria_box = "a_favor" if valor_box == "no" else "excepciones" if valor_box == "si" else "ambiguas"
            box[categoria_box].append({"id": f["id"], "operador": f["operador"],
                                       "sin_alerta_normativa": f["id"] in limpios,
                                       "edad": int(f["edad"]), "nivel": int(f["nivel"]), "box_antes": valor_box})
        if ";" in f["credenciales"] and normalizar(f["lesion_trabajo"]) == "no":
            partes = f["credenciales"].split(";")
            if len(partes) != 2 or sum("(prepaga)" in normalizar(x) for x in partes) != 1 or sum("(obra social)" in normalizar(x) for x in partes) != 1:
                dos["ambiguas"].append({"id": f["id"]})
                continue
            prepaga = next(x for x in partes if "(prepaga)" in normalizar(x)).split(" (prepaga)")[0].strip()
            obra = next(x for x in partes if "(obra social)" in normalizar(x)).split(" (obra social)")[0].strip()
            entidad = f["entidad_verificada"]
            categoria = "a_favor" if normalizar(entidad) == normalizar(prepaga) else "excepciones" if normalizar(entidad) == normalizar(obra) else "ambiguas"
            dos[categoria].append({"id": f["id"], "operador": f["operador"],
                                   "sin_alerta_normativa": f["id"] in limpios,
                                   "tipo_verificado": "prepaga" if categoria == "a_favor" else "obra_social" if categoria == "excepciones" else "otro",
                                   "prepaga_primera": "(prepaga)" in normalizar(partes[0])})
    return {"voluntariado_75_sin_acompanante": voluntariado,
            "prioridad_prepaga_dos_credenciales": dos,
            "registro_antes_box_no_obligatorio": box}


def validar_umbrales(filas):
    """Ajusta el umbral por separado en IDs pares e impares y evalúa en el otro grupo."""
    def error(grupo, umbral):
        return sum((int(f["edad"]) >= umbral and not f["acompanante"]) !=
                   (normalizar(f["aviso_al_voluntariado"]) == "si") for f in grupo)
    salida = []
    for paridad in (0, 1):
        ajuste = [f for f in filas if int(f["id"].split("-")[-1]) % 2 == paridad]
        prueba = [f for f in filas if int(f["id"].split("-")[-1]) % 2 != paridad]
        minimo = min(error(ajuste, n) for n in range(18, 90))
        mejores = [n for n in range(18, 90) if error(ajuste, n) == minimo]
        salida.append({"ajuste_paridad": paridad, "n_ajuste": len(ajuste), "umbrales_optimos": mejores,
                       "errores_ajuste": minimo, "n_prueba": len(prueba),
                       "errores_prueba_por_umbral": {str(n): error(prueba, n) for n in mejores}})
    return salida


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historial", type=Path, default=Path("historial/historial.csv"))
    parser.add_argument("--parametros", type=Path, default=Path("normas/original/parametros.yaml"))
    parser.add_argument("--salida", type=Path, default=Path("resultados/exploracion_costumbres.json"))
    parser.add_argument("--evidencias", type=Path, default=Path("resultados/evidencias_costumbres.json"))
    args = parser.parse_args()
    with args.historial.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    resultado = {"historial_sha256": hashlib.sha256(args.historial.read_bytes()).hexdigest(),
                 "parametros_sha256": hashlib.sha256(args.parametros.read_bytes()).hexdigest(),
                 "reglas_sha256": hashlib.sha256(Path(__file__).with_name("reglas.py").read_bytes()).hexdigest(),
                 "exploracion_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 "grupos": explorar(filas, parametros(args.parametros)),
                 "validacion_umbrales": validar_umbrales(filas)}
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.evidencias.parent.mkdir(parents=True, exist_ok=True)
    args.evidencias.write_text(json.dumps(evidencias(filas, parametros(args.parametros)), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Análisis guardado en {args.salida}; evidencia por ID en {args.evidencias}")


if __name__ == "__main__":
    main()
