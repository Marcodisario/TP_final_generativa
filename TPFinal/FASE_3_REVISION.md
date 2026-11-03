# Fase 3 — Revisión de reglas y candidatas a error

## Alcance

Se aplicaron las reglas del grupo a las 2.000 filas, se compararon sus hallazgos con las normas originales y se revisó al menos un ejemplo de cada tipo de violación informado. Es una revisión inicial basada en la hipótesis de que el historial usa las normas originales y de que sus columnas reflejan la situación pertinente al registrar. No es una auditoría manual individual de las 2.000 filas ni una clasificación definitiva.

## Corrección encontrada: dos credenciales

La primera implementación usaba una expresión regular que podía interpretar dos credenciales separadas por `;` como una sola entidad. Por ejemplo, en `H-0010` había una obra social y una prepaga, y el programa construía un supuesto nombre que incluía partes de ambas. Eso producía alertas falsas.

El historial contiene **193 filas con dos credenciales**. La norma revisada no establece aquí cuál seleccionar cuando se presentan dos; podría existir una costumbre, que se debe investigar sin asumirla. Ahora esas comparaciones de cobertura quedan como `insuficiente`. Otras reglas independientes de esas mismas filas siguen evaluándose. En `H-0010`, por ejemplo, se conserva la alerta del plazo de ECG: llegó en ambulancia y figura 10 minutos, frente a 5 según TDE-01 y TDE-04 con parámetros originales.

Se agregó una prueba para impedir que el problema de interpretación reaparezca. Los recuentos originales de la fase 2 no deben usarse: incluían esa falla.

## Resultado del análisis actual

Comando, ejecutado desde `TPFinal`:

```powershell
uv run python -m curado.revisar
```

| Estado de revisión | Filas | Interpretación |
|---|---:|---|
| `candidata_error` | 238 | Al menos una comparación señala una posible violación normativa. No es una etiqueta final. |
| `pendiente` | 174 | No hay violación detectada, pero al menos una comparación quedó sin información suficiente. |
| `sin_alertas` | 1.588 | Las comparaciones implementadas no informaron violaciones ni insuficiencias. No prueba que la fila sea correcta: faltan reglas no observables y costumbres. |

En total, **193 filas tienen alguna comparación insuficiente**. De ellas, 19 aparecen como `candidata_error` porque tienen una posible violación independiente, y 174 como `pendiente`. Los grupos de la tabla son mutuamente excluyentes.

| Regla con posible violación | Comparaciones señaladas | Fuente principal |
|---|---:|---|
| Plazo del circuito | 97 | NOR-TDE-01–04 |
| Tipo de registro | 64 | NOR-ADM-01 y NOR-ADM-03 |
| Box antes del registro | 61 | NOR-ADM-01 y NOR-ADM-02 |
| Cobertura | 11 | NOR-COB-01–04 |
| Entidad a notificar | 5 | NOR-COB-01–04 |

Las cantidades por regla cuentan comparaciones y pueden superponerse en una misma fila; no deben sumarse como cantidad de pacientes distintos. El resumen generado incluye SHA-256 del historial, parámetros y código de reglas para identificar lo usado.

## Ejemplos revisados

- `H-0014`: pasaporte, nivel 2 y registro definitivo. Con `P-ADM-3 = 2`, NOR-ADM-03 indica provisorio con el número del documento. El programa señala el tipo de registro.
- `H-0040`: edad 68 y `box_antes_del_registro = no`. Con `P-ADM-2 = 67`, NOR-ADM-02 indica box antes del registro. El programa señala ese campo.
- `H-0010`: dolor torácico, llegada en ambulancia y plazo registrado de 10 minutos. Con `P-TDE-1 = 10` y `P-TDE-5 = 5`, el plazo calculado es 5. La selección de cobertura permanece pendiente por sus dos credenciales.
- `H-0555`: el número de obra social declarado termina en 7 y la ficha indica `obra_social`; con `P-COB-2 = 7`, NOR-COB-04 indica `sin_cobertura` y notificar a la entidad. El programa señala la cobertura.
- `H-0378`: el número declarado termina en 7 y la afiliación figura inactiva, pero no se indica entidad a notificar. NOR-COB-04 exige notificar igualmente; el programa señala la notificación.
- `H-0003`: también tiene terminación 7 y respuesta inactiva, pero registra `sin_cobertura` y notifica a la entidad. Es un ejemplo compatible con esa excepción, no una infracción por notificar a una entidad inactiva.

## Archivos generados y cómo usarlos

- `resultados/revision_normativa.csv`: todas las filas con estado de revisión, reglas señaladas, normas, detalles y reglas pendientes.
- `resultados/resumen_revision.json`: recuentos y huellas SHA-256.
- `resultados/reglas_historial.jsonl`: detalle de cada comparación. Se genera con `uv run python -m curado.analizar --salida resultados/reglas_historial.jsonl`.

La carpeta `resultados/` está ignorada por Git; los archivos se regeneran con los comandos anteriores. Antes de reportar resultados finales se deberán conservar las evidencias que exige el enunciado y fijar los archivos y versiones correspondientes.

## Pendientes antes de la clasificación final

1. Confirmar con la cátedra o la documentación del origen que las normas originales corresponden al historial y cómo se representan los posibles cambios de nivel y documento.
2. Profundizar la revisión de candidatas y analizar los datos insuficientes; el archivo no reemplaza una revisión de evidencia.
3. Investigar las dos credenciales y el aviso al voluntariado como posibles costumbres, contrastando grupos y excepciones con IDs. No asumir una costumbre por la mayoría sin revisar casos comparables.
4. Tratar como pendientes las obligaciones que el CSV no permite verificar, como la secuencia y los tiempos de trámites. Revisar la interpretación de respuestas atípicas de ART.
5. Solo después de revisar normas y costumbres construir `historial_clasificado.csv` con `correcta`, `error` y `ruido`.
