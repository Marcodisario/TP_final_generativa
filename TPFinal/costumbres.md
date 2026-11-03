# Costumbres del hospital: hipótesis basadas en el historial

Este documento describe patrones detectados en `historial/historial.csv`, no respuestas oficiales. Las normas no definen expresamente el aviso al voluntariado ni una prioridad para elegir entre dos credenciales. En el caso del box, NOR-ADM-01 §4 permite registrar mientras el paciente espera cuando no aplica la obligación de ir primero al box; no dice que esa sea la única opción.

Los análisis usan las normas y parámetros originales como hipótesis. Los recuentos principales incluyen las 2.000 filas, incluso aquellas con alertas normativas en otros campos; también se informa una comprobación excluyendo esas alertas. Una alerta normativa no implica necesariamente que todos los demás campos estén mal. Los patrones pueden cambiar con evidencia nueva y no deben aplicarse sin verificar la situación concreta.

## 1. Aviso al voluntariado: edad y acompañante

**Hipótesis:** se avisa al voluntariado cuando el paciente tiene **75 años o más y no tiene acompañante**; en los demás casos no se avisa.

| Situación según hipótesis | Aviso `sí` | Aviso `no` |
|---|---:|---:|
| Edad ≥ 75 y sin acompañante | 207 | 19 |
| Resto de las situaciones | 132 | 1.642 |

En total, **1.849 de 2.000** filas coinciden con la hipótesis y **151** se apartan. Las 151 excepciones corresponden a los operadores OP-04 (38), OP-11 (60) y OP-17 (53). Los otros 17 operadores coinciden en sus filas, pero no debe asumirse que pertenecer a esos operadores convierte automáticamente cualquier caso en ruido.

Ejemplos que cumplen la condición y registran aviso: `H-0013`, `H-0016`, `H-0036`, `H-0044`, `H-0045`, `H-0063`. Ejemplos que se apartan del patrón: `H-0005`, `H-0006`, `H-0009`, `H-0053`, `H-0056`, `H-0067`. Los datos de todos los IDs, incluida edad, acompañante, decisión y operador, están en `evidencias/curado/evidencias_costumbres.json`, bajo `voluntariado_75_sin_acompanante`.

Para poner a prueba el umbral, se buscaron valores de 18 a 89 años por separado en IDs pares e impares, siempre con la condición de no tener acompañante. Ambos grupos seleccionaron 75 como umbral con menos desacuerdos; al evaluar el umbral obtenido en el otro grupo hubo 66 y 85 discrepancias, respectivamente, sobre 1.000 filas. Es una comprobación interna: los grupos provienen del mismo historial y esto no demuestra que la hipótesis generalice a otros datos. Tampoco compara todas las reglas alternativas posibles.

## 2. Dos credenciales: prioridad de la prepaga

**Hipótesis:** cuando el paciente presenta una credencial de prepaga y otra de obra social y no es un caso laboral, se verifica la prepaga.

Hay **193 filas** con esas dos credenciales. En **184** se verificó la entidad de prepaga y en **9** la obra social. En 100 de las 184 coincidencias la prepaga aparecía primera en el campo y en 84 aparecía segunda: la pauta no se explica simplemente por elegir la primera.

Ejemplos a favor: `H-0010`, `H-0011`, `H-0021`, `H-0052`, `H-0056`, `H-0075`. Las nueve excepciones son `H-0334`, `H-0404`, `H-0408`, `H-0480`, `H-0792`, `H-0881`, `H-1190`, `H-1467` y `H-1520`. Pertenecen a OP-04, OP-11 y OP-17, pero esta concentración no demuestra por sí sola el motivo de cada decisión.

Al excluir filas con alertas normativas de otras reglas, quedan 174 casos de dos credenciales: 165 verifican prepaga y 9 obra social. El análisis compara **la entidad elegida**, no confirma por sí solo que el número verificado sea correcto ni que los otros campos de la ficha sean correctos. Los 193 IDs y el orden de presentación están en `evidencias/curado/evidencias_costumbres.json`, bajo `prioridad_prepaga_dos_credenciales`.

La prioridad de ART en lesiones laborales sí está escrita en NOR-COB-02 §5 y prevalece sobre esta hipótesis.

## 3. Registro antes del box cuando no es obligatorio lo contrario

**Patrón observado, pendiente de confirmar como costumbre:** en las filas con edad menor que `P-ADM-2` y nivel mayor que `P-ADM-1`, se registra antes de pasar al box. Con los parámetros originales esto corresponde a edad menor de 67 y nivel mayor que 2.

En **582 de 582** filas de ese grupo figura `box_antes_del_registro = no`; **547** permanecen al excluir filas con alguna alerta normativa en otros campos. La pauta aparece en los 20 operadores en el subconjunto sin esas alertas. Ejemplos: `H-0007`, `H-0009`, `H-0018`, `H-0026`, `H-0035`, `H-0039`, `H-0042`, `H-0051`.

La norma permite registrar mientras se espera y no obliga a hacerlo en ese orden, por lo que este patrón puede ser una convención del hospital. Sin embargo, la ausencia total de excepciones también podría reflejar cómo se generaron o registraron los datos: **no alcanza para afirmar que sea una costumbre confirmada** ni para clasificar casos externos. Los IDs están en `evidencias/curado/evidencias_costumbres.json`, bajo `registro_antes_box_no_obligatorio`.

## Reproducir y revisar las evidencias

Desde `TPFinal`:

```powershell
uv run python -m curado.explorar_costumbres --salida evidencias/curado/exploracion_costumbres.json --evidencias evidencias/curado/evidencias_costumbres.json
```

El script genera `evidencias/curado/exploracion_costumbres.json` con recuentos por grupo y hashes de entrada y código, y `evidencias/curado/evidencias_costumbres.json` con los IDs a favor, excepciones y casos ambiguos. Cada entrada identifica si tiene una alerta normativa detectada por las reglas actuales. Los archivos pueden incluirse en Git y regenerarse con el comando.

En la fase 5 se generó una clasificación **provisional** que aplica las dos primeras hipótesis, con prioridad para violaciones normativas. El patrón del box sigue siendo exploratorio y no se usa para asignar ruido. Este análisis explora las tres hipótesis indicadas; no garantiza haber descubierto todas las costumbres del historial. La clasificación todavía necesita revisión antes de tomarse como entrega definitiva.
