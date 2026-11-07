# Checklist — Parte 1: clasificación y costumbres

> Actualización: el grupo aceptó la clasificación como definitiva. Los puntos de revisión que siguen documentan las comprobaciones y limitaciones identificadas durante el desarrollo; no son una nueva solicitud de aprobación.

Alcance: clasificación, costumbres y una primera conversión de trazas del historial. La generación de conversaciones sintéticas queda para una decisión posterior; este checklist no declara completa toda la parte 1 de la misión.

## Entregables y formato

- [x] `historial_clasificado.csv` existe y contiene las columnas `id,tipo`.
- [x] Contiene los 2.000 IDs del historial una sola vez y solo `correcta`, `error` o `ruido`.
- [x] `costumbres.md` explica las hipótesis e indica IDs de respaldo y excepciones.
- [x] `INFORME.md` contiene un apartado preliminar de curado, método, cantidades y pasadas del desarrollo.
- [x] `resumen_parte1.md` explica el recorrido y cómo ejecutar los scripts.
- [x] Las 1.600 trazas etiquetadas `correcta` se convirtieron al formato de conversación del agente de ejemplo; el conjunto es provisional y no incluye las 800 trazas de referencia.
- [x] `CONVERSACIONES_ENTRENAMIENTO.md` describe el formato y el comando de reproducción; `entrenamiento/resumen_conversion.json` registra cantidades y hashes.
- [ ] Optimizar el prompt antes de entrenar y preparar el archivo y la división de evaluación para una corrida concreta.

## Lógica y revisión

- [x] Las reglas contemplan excepciones de documentos, box, circuitos, ART y afiliaciones de terminación reservada.
- [x] Los parámetros se leen de `normas/original/parametros.yaml`.
- [x] Una posible violación normativa prevalece sobre una desviación de costumbre.
- [x] La clasificación no usa el operador como etiqueta.
- [x] El clasificador no actualiza el CSV si encuentra comparaciones sin información suficiente; deja la traza para revisión.
- [x] Las dos hipótesis de costumbres usadas y el patrón exploratorio de box están diferenciados.
- [ ] Confirmar que las normas originales y la interpretación temporal de las columnas corresponden al historial.
- [ ] Revisar las candidatas a error, las excepciones a las costumbres y las reglas no verificables con el CSV.
- [ ] Validar las hipótesis de costumbre y explorar si hay otras; no hay clasificación verdadera de referencia disponible.
- [x] El grupo revisó y aceptó la clasificación como definitiva para su trabajo.

## Auditabilidad

- [x] Se guardaron trazas por fila, recuentos, IDs de respaldo y hashes en `evidencias/curado/`, que no está ignorada por Git.
- [x] Los scripts y comandos para regenerar esas evidencias y el CSV están documentados.
- [x] Se conservó documentado el error inicial de lectura de dos credenciales y su corrección.
- [ ] Incorporar los archivos y evidencias al historial de Git con commits apropiados: todavía no están todos versionados.

Este checklist no certifica exactitud frente a la clasificación secreta de la cátedra ni cubre los demás requisitos de entrega del trabajo.
