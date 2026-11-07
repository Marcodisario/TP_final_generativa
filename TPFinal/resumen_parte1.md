# Resumen de la parte 1: curado e ingeniería de datos

> Actualización: el grupo confirmó que acepta como definitiva la clasificación del historial. Las referencias a resultados provisionales describen cómo se trabajó antes de esa confirmación.

## Objetivo

El historial contiene 2.000 admisiones sin etiquetas. La misión pide clasificar cada fila como `correcta`, `error` o `ruido`, explicar las costumbres con IDs que las respalden y convertir las filas útiles en conversaciones de entrenamiento. También permite crear conversaciones sintéticas.

## Cómo trabajamos hasta ahora

1. **Entendimos los datos y las normas.** Revisamos las columnas del historial, las normas originales y los parámetros. Distinguimos los hechos del paciente, lo que el operador verificó y la ficha que registró. El mapa inicial está en `FASE_1_MAPA.md`.
2. **Tradujimos las normas a reglas.** En `curado/reglas.py` comprobamos registro, box, circuitos, plazos, cobertura y verificación, incluyendo excepciones como pasaporte en triage urgente, ART y terminación reservada. Cada comparación devuelve una explicación y puede ser compatible, una posible violación o insuficiente.
3. **Revisamos las primeras alertas.** Detectamos y corregimos un error propio: el programa confundía dos credenciales con una sola. Documentamos ejemplos y límites en `FASE_3_REVISION.md`. Antes de integrar las costumbres, había 238 filas con posibles violaciones, 174 pendientes sin violaciones y 1.588 sin alertas.
4. **Investigamos costumbres.** El análisis encontró dos hipótesis fuertes: avisar al voluntariado si el paciente tiene al menos 75 años y no tiene acompañante, y priorizar la prepaga cuando hay también una obra social en un caso no laboral. Otro patrón sobre el orden de registro y box quedó solo como exploratorio. `costumbres.md` explica la evidencia, excepciones y limitaciones.
5. **Integramos ambas fuentes.** Generamos `historial_clasificado.csv` y una traza por fila. Las violaciones normativas tienen prioridad: si una fila viola una norma y se aparta de una costumbre, se etiqueta como `error`. Si no hay violación y se aparta de una de las dos costumbres utilizadas, se etiqueta como `ruido`; el resto queda `correcta` según las reglas actuales.
6. **Convertimos las trazas útiles.** Con la clasificación provisional, tomamos las 1.600 filas `correcta` y transformamos sus trazas en conversaciones de mensajes del sistema, usuario y asistente, respetando el formato del README. Los pasos y respuestas se conservan sin inventar contenido. El detalle está en `CONVERSACIONES_ENTRENAMIENTO.md`.

## Resultado provisional de la fase 5

| Tipo | Cantidad |
|---|---:|
| `correcta` | 1.600 |
| `error` | 240 |
| `ruido` | 160 |
| **Total** | **2.000** |

De los 160 casos señalados por las costumbres, 151 se apartan de la hipótesis de voluntariado y 9 de la prioridad de prepaga; en este historial no se superponen entre sí ni con las alertas normativas. Al examinar las dos credenciales y aplicar las normas a la efectivamente verificada, aparecieron dos posibles violaciones más que en el conteo previo: `H-0929` y `H-1401`. No se utiliza el operador como criterio de clasificación.

La etiqueta `correcta` significa que no se encontró una violación con las reglas y dos hipótesis actuales; **no demuestra que la fila sea correcta según la clasificación secreta**. El análisis presupone que al historial le corresponden las normas originales y que las columnas reflejan la situación pertinente al registrar. La ficha no muestra toda la secuencia de eventos. Las costumbres son inferencias y pueden existir otras; por eso hay que revisar los resultados antes de la entrega.

La traza no registra pendientes de datos en esta corrida según las comprobaciones implementadas. Esto no significa que todos los supuestos anteriores hayan sido confirmados ni que se hayan auditado las 2.000 filas manualmente. Si una corrida futura encuentra una comparación insuficiente, la traza marca `revisar: true` y el programa no actualiza el CSV hasta resolverla.

## Reproducir

Desde `TPFinal`, con el entorno instalado con `uv sync`:

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m curado.revisar --salida evidencias/curado/revision_normativa.csv --resumen evidencias/curado/resumen_revision.json
uv run python -m curado.explorar_costumbres --salida evidencias/curado/exploracion_costumbres.json --evidencias evidencias/curado/evidencias_costumbres.json
uv run python -m curado.clasificar --trazas evidencias/curado/trazas_clasificacion.jsonl --resumen evidencias/curado/resumen_clasificacion.json
uv run python -m curado.convertir_trazas
```

- `curado.revisar` genera la revisión normativa inicial.
- `curado.explorar_costumbres` genera los recuentos y los IDs de respaldo y excepciones.
- `curado.clasificar` genera `historial_clasificado.csv` y, con las opciones indicadas, `evidencias/curado/trazas_clasificacion.jsonl` y `evidencias/curado/resumen_clasificacion.json`, con recuentos y huellas SHA-256 de entradas, código y CSV.
- `curado.convertir_trazas` genera `entrenamiento/conversaciones_historial.jsonl` y `entrenamiento/resumen_conversion.json` a partir de las trazas etiquetadas `correcta`.
- Los archivos de `evidencias/curado/` pueden incluirse en Git y regenerarse con los comandos indicados. `resultados/` sigue ignorado para corridas locales.

Se verificó que el CSV tenga las columnas `id,tipo`, los 2.000 IDs del historial exactamente una vez y únicamente las tres etiquetas permitidas. Las pruebas automatizadas cubren normas, excepciones, prioridad de clasificación y el bloqueo de exportación ante datos insuficientes.

## Qué falta de la parte 1

- Revisar las hipótesis, las candidatas y las limitaciones de la clasificación provisional.
- Revisar la selección provisional y, una vez optimizado el prompt, regenerar las conversaciones para el entrenamiento y fijar la división de evaluación.
- Si conviene, generar y validar conversaciones sintéticas. Esta parte es opcional.
- Documentar cantidades, scripts y decisiones finales en el informe del trabajo.
