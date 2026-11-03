# Fase 2: reglas normativas

## Qué hace

`curado/reglas.py` transforma algunas normas escritas en comparaciones explicables para cada fila. Cada resultado incluye la regla, la norma, un estado y una explicación. El programa **no** identifica costumbres ni genera `historial_clasificado.csv`.

- `violacion`: los datos usados contradicen la interpretación implementada de la norma.
- `compatible`: la comparación concreta no encontró contradicción; no significa que toda la fila sea correcta.
- `insuficiente`: esa regla no puede decidirse con los datos o el formato disponibles.

Las reglas se basan en la hipótesis de que el historial corresponde a las normas originales y que las columnas resumen la situación relevante al registrar. Esa hipótesis debe verificarse. El CSV no aporta una historia completa de cambios, retriage o presentación posterior de documentos: las violaciones son candidatas sujetas a revisión, no etiquetas finales automáticas.

## Cómo está organizado

1. `parametros` lee `parametros.yaml`: así las condiciones numéricas no están escritas en cada regla.
2. `identidad_y_box` aplica identificación, excepciones por pasaporte/cédula y el orden box-registro.
3. `circuitos` deduce el circuito desde el triage y después el plazo, con el ajuste por ambulancia.
4. `cobertura` interpreta la cobertura de origen, aplica prioridad de ART, verifica entidad y número y contempla la terminación reservada.
5. `evaluar_fila` reúne los resultados. No verifica voluntariado: eso requiere investigar costumbres.

El análisis de cobertura reconoce los formatos observados en el CSV. Si una declaración no se puede interpretar, devuelve `insuficiente`. Cuando se verificó otra entidad o número, la respuesta recibida no demuestra si la afiliación correcta está activa: por eso no se deduce el estado de cobertura ordinaria a partir de esa respuesta. En el caso ART se aplica la cobertura y notificación indicadas por la norma; hay que revisar cómo interpretar cualquier respuesta atípica de una ART.

Corrección de fase 3: cuando hay dos credenciales, el programa ya no concatena ambas como si fueran una entidad. Marca la selección y sus consecuencias como `insuficiente`, pendientes de estudiar como posible costumbre.

## Cómo probarlo

Desde la carpeta `TPFinal`, después de `uv sync`:

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m curado.analizar --id H-0001
uv run python -m curado.analizar --salida resultados/reglas_historial.jsonl
```

El último comando escribe un objeto JSON por fila, con los resultados detallados. Se puede ejecutar con otro archivo de parámetros mediante `--parametros ruta/parametros.yaml`, pero solo tiene sentido aplicar una versión normativa adecuada al origen del historial.

Los resultados de fase 2 no son la clasificación verdadera: en fase 3 hay que revisar violaciones y supuestos, y en fases posteriores investigar el ruido y las costumbres. Tampoco se verifican obligaciones temporales o preguntas que el CSV no registra.
