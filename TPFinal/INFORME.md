# Informe del trabajo final

## Parte 1: curado del historial — estado preliminar

### Fuente y método

Se analizaron las 2.000 filas de `historial/historial.csv` contra las normas originales y sus parámetros. `curado/reglas.py` implementa comparaciones para identidad, orden de box, circuitos, plazos y cobertura. Las violaciones normativas prevalecen sobre las desviaciones de costumbres. El análisis asume que las normas originales corresponden al historial y que las columnas representan la situación pertinente al registrar; la secuencia completa de eventos no está disponible.

### Pasadas del desarrollo

1. Se relevaron columnas, normas, excepciones y límites de observación (`FASE_1_MAPA.md`).
2. Se implementaron reglas y se inspeccionaron sus resultados (`FASE_2_REGLAS.md`).
3. Se corrigió una interpretación errónea de filas con dos credenciales, que inicialmente producía falsas alertas de entidad. Se revisaron ejemplos de cada clase de alerta (`FASE_3_REVISION.md`).
4. Se exploraron las decisiones sobre voluntariado y dos credenciales. Se formularon hipótesis de edad/acompañante y preferencia de prepaga, con sus excepciones. También se registró como exploratorio un patrón de orden box-registro (`costumbres.md`).
5. Se integraron las reglas con las dos primeras hipótesis en `curado/clasificar.py`. Las filas con dos credenciales se contrastan con las normas aplicables a la entidad efectivamente verificada; la elección de obra social frente a prepaga se analiza como posible ruido.
6. En la revisión actual se impidió actualizar el CSV si alguna fila queda con datos insuficientes y se guardaron las evidencias en una carpeta que puede incluirse en Git. Las etiquetas siguen siendo provisionales: el bloqueo de datos insuficientes no confirma los supuestos ni reemplaza la revisión humana.

### Resultado provisional

| Tipo | Filas |
|---|---:|
| `correcta` | 1.600 |
| `error` | 240 |
| `ruido` | 160 |

Los 160 casos de ruido corresponden a 151 discrepancias de la hipótesis de voluntariado y 9 de la preferencia de prepaga; en esta corrida no se superponen con errores detectados. Las hipótesis, sus conteos, IDs y excepciones se detallan en `costumbres.md` y `evidencias/curado/`. No se conoce la clasificación verdadera de la cátedra, por lo que estos números no miden exactitud.

### Reproducción y límites

Los comandos, archivos producidos y pruebas están en `resumen_parte1.md`. `evidencias/curado/trazas_clasificacion.jsonl` conserva por ID las comparaciones normativas, las violaciones, las desviaciones de costumbre y los pendientes. El resumen contiene hashes de entradas, código y CSV. Se debe conservar en el repositorio la versión exacta de código y datos correspondiente a las evidencias.

Pendientes: confirmar que la versión de normas aplica al historial, revisar candidatas y excepciones, y validar las costumbres y otros patrones no explorados. La creación de conversaciones de entrenamiento y datos sintéticos queda fuera de esta revisión; debe documentarse cuando se realice.

Las demás partes del informe se completarán al desarrollarlas.
