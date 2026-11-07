# Conversaciones del historial para entrenamiento

## Qué se hizo

Se convierten las trazas de `historial/trazas.jsonl` que corresponden a filas etiquetadas `correcta` en `historial_clasificado.csv`. Con la clasificación revisada y dada por definitiva por el grupo salen **1.600 conversaciones**; se excluyen 240 filas `error` y 160 `ruido`. Si en el futuro se modifica el archivo de clasificación, las conversaciones deben regenerarse.

No se modifican las decisiones, argumentos o respuestas guardadas en las trazas. Se comprueba que, en cada traza seleccionada, el orden de los pasos sea válido, la ficha coincida con la fila y la llamada final, y la afiliación verificada coincida con el historial. Estas comprobaciones no prueban que la decisión sea correcta ni revisan toda la calidad de cada razonamiento.

## Formato

`entrenamiento/conversaciones_historial.jsonl` contiene un objeto por línea con `id`, `paciente_id` y `messages`. Los dos identificadores permiten rastrear la conversación hasta su fuente; `messages` contiene la conversación de entrenamiento:

1. `system`: mensaje de sistema del agente de ejemplo de la cátedra.
2. `user`: aviso de ingreso del paciente, con el texto de `primer_mensaje`.
3. Para cada paso, `assistant`: JSON con `herramienta` y `argumentos`.
4. Después de cada llamada excepto `registrar_decision`, `user`: `Resultado de <herramienta>:\n` y el resultado original.

El último mensaje es la llamada a `registrar_decision`, sin un resultado posterior, como indica el README del kit. Un entrenamiento que acepte únicamente el campo `messages` puede descartar los identificadores después de conservarlos para auditoría.

El prompt usado es **una referencia sin optimizar** tomada de `admision.ejemplo.mensaje_de_sistema()`, no el prompt final del grupo. La misión pide optimizarlo con el modelo sin entrenar antes de entrenar; una vez elegido el prompt final, hay que regenerar o transformar las conversaciones y conservar la versión y el archivo exactos usados en cada corrida.

## Reproducir

Desde `TPFinal` con el entorno instalado mediante `uv sync`:

```powershell
uv run python -m curado.convertir_trazas
uv run python -m unittest discover -s tests -v
```

El convertidor lee `historial/historial.csv`, `historial_clasificado.csv` y `historial/trazas.jsonl`; genera `entrenamiento/conversaciones_historial.jsonl` y `entrenamiento/resumen_conversion.json`, con cantidades y hashes del código, las entradas, el prompt y el resultado. La conversión es determinista y no usa semilla. Valida antes de escribir los archivos; si falta un ID, hay duplicados o una traza seleccionada es inconsistente, termina con un error.

`entrenamiento/trazasE.jsonl` es el archivo presente con las 800 trazas de referencia; el README del kit lo llama `entrenamiento/trazas.jsonl`. Se dejó intacto y no se incorporó a estas 1.600 conversaciones. Contiene trazas con valores de normas variados y puede evaluarse más adelante para una estrategia de entrenamiento, sin asumir que ya forma parte del conjunto generado.

Por ahora no hay división de entrenamiento/validación ni datos sintéticos, ni se entrenó ningún modelo. Antes de una corrida se deberá fijar la división y sus archivos exactos, verificar que no haya contaminación con la evaluación y conservar la configuración, prompt y datos utilizados.
