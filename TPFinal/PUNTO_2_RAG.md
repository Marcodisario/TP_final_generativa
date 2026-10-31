# Parte 2: buscador propio (RAG)

## Objetivo

El buscador recupera la evidencia normativa que necesita el agente sin memorizar
los valores de la versión de práctica. El índice se reconstruye en
`construir_buscador(ruta_normas)` y lee tanto los archivos `NOR-*.md` como el
`parametros.yaml` de la carpeta recibida.

## Diseño

- Indexación léxica local, sin APIs ni modelos externos.
- Normalización de acentos, plural y flexiones frecuentes del español.
- BM25 por párrafo, reforzado con coincidencias de frases y vocabulario del
  dominio (por ejemplo, "dado de baja" y "afiliación inactiva").
- Recuperación jerárquica: secciones completas para la herramienta del agente y
  párrafos para la comparación con presupuestos fijos de tokens.
- Cantidad adaptativa: devuelve una sección para consultas claras y dos cuando
  detecta una interacción entre normas o una ambigüedad relevante.
- Parámetros dinámicos: cada fragmento incorpora solamente los valores que cita.
  También expande rangos como `P-GUA-1 a P-GUA-5`.

La implementación está en `buscador_rag.py`; `entrega.py` expone el contrato que
usa la cátedra. `construir_agente()` queda expresamente pendiente para las partes
3 y 4 y no participa en la evaluación separada del RAG.

## Reproducir

Pruebas del contrato y de las tres versiones de parámetros:

```powershell
python -m unittest -v test_buscador_rag.py
```

Evaluación oficial en pantalla:

```powershell
python -m admision.evaluar_rag --entrega entrega.py --normas normas/original --consultas rag/consultas_dev.jsonl
```

La misma evaluación, guardando el artefacto auditable:

```powershell
python evaluar_buscador.py --entrega entrega.py --normas normas/original --consultas rag/consultas_dev.jsonl --salida resultados/rag_original.json
```

## Resultado de desarrollo

Con `k_entorno = 2`, sobre las 60 consultas provistas:

- Recall de evidencia: **1,000**.
- Precisión: **0,933**.
- Chunks por consulta: **1,27**.
- Tokens por consulta: **377**.
- Consultas con toda la evidencia: **60 de 60**.
- Recall por tipo: **1,000** en directa, coloquial, numérica, dos secciones y
  distractora.

Comparación con la referencia BM25 de la cátedra:

- Recall: 1,000 propio frente a 0,875 de referencia.
- Precisión: 0,933 propio frente a 0,492 de referencia.
- Contexto: 377 tokens propios frente a 580 de referencia.
- Consultas completas: 60/60 propias frente a 51/60 de referencia.

Con presupuestos fijos, el resultado fue:

- 256 tokens: recall 0,883; precisión 0,286; 51/60 completas.
- 512 tokens: recall 0,950; precisión 0,170; 57/60 completas.
- 1024 tokens: recall 1,000; precisión 0,091; 60/60 completas.

Estos valores son resultados del conjunto de desarrollo conocido, no del test
secreto ni del agente completo. El siguiente control necesario es medir cuántos
casos resuelve el agente con este buscador y comparar costo y tiempo por caso.

