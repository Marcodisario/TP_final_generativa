# Comparación de RAG: actual, léxico general y embeddings LSA

## Objetivo

Se construyeron cuatro alternativas al RAG actual para reducir el sobreajuste a
las 60 consultas de desarrollo:

1. **RAG léxico general:** BM25 por documento y apartado, n-gramas de
   caracteres, títulos y selección genérica por cobertura. No contiene reglas
   que asignen frases a códigos `NOR-*`.
2. **RAG léxico-semántico:** diccionario bidireccional de conceptos del dominio,
   BM25 por campos, bigramas, n-gramas, cobertura conceptual, segmentación de
   consultas y referencias del corpus. No asigna frases a códigos `NOR-*`.
3. **RAG de embeddings LSA:** representación TF-IDF de palabras y caracteres
   proyectada a 64 dimensiones densas mediante `TruncatedSVD`. Se entrena
   exclusivamente con las normas recibidas.
4. **RAG híbrido con reranking:** genera candidatos con los tres recuperadores
   anteriores, aplica Reciprocal Rank Fusion y reordena por cobertura léxica y
   conceptual, títulos, frases, apartados y referencias del corpus.

Ninguna alternativa utiliza las preguntas nuevas durante la construcción del
índice o la elección de sus reglas. Después de la primera medición del holdout
no se reajustaron pesos ni umbrales.

## Resultados principales

### Conjunto oficial de 60 preguntas conocidas

| RAG | Recall | Precisión | Completas | Chunks/consulta | Tokens/consulta |
|---|---:|---:|---:|---:|---:|
| Actual con heurísticas | 1,000 | 0,933 | 60/60 | 1,27 | 377 |
| Léxico general | 0,808 | 0,700 | 47/60 | 1,43 | 444 |
| Léxico-semántico | 0,867 | 0,642 | 51/60 | 1,70 | 514 |
| Embeddings conceptuales LSA | 0,842 | 0,758 | 49/60 | 1,35 | 382 |
| Híbrido + reranking | 0,858 | 0,625 | 50/60 | 1,68 | 511 |

### Holdout de 60 preguntas nuevas

Las métricas del holdout miden recuperación de documentos: 52 consultas
requieren una norma y 8 requieren dos.

| RAG | Recall documental | Precisión documental | Completas | Chunks/consulta | Tokens/consulta |
|---|---:|---:|---:|---:|---:|
| Actual con heurísticas | 0,700 | 0,625 | 39/60 | 1,32 | 376 |
| Léxico general | 0,775 | 0,608 | 44/60 | 1,50 | 424 |
| Léxico-semántico | 0,917 | 0,625 | 54/60 | 1,78 | 510 |
| Embeddings conceptuales LSA | 0,908 | 0,725 | 52/60 | 1,53 | 442 |
| Híbrido + reranking | 0,908 | 0,642 | 53/60 | 1,72 | 502 |

### Rendimiento computacional observado

| RAG | Construcción | Latencia media | p95 |
|---|---:|---:|---:|
| Actual con heurísticas | 13 ms | 0,14 ms | 0,18 ms |
| Léxico general | 46 ms | 2,88 ms | 3,60 ms |
| Léxico-semántico | 123 ms | 7,00 ms | 13,14 ms |
| Embeddings conceptuales LSA | 892 ms | 24,80 ms | 44,50 ms |
| Híbrido + reranking | 1323 ms | 53,84 ms | — |

Los tiempos corresponden a una corrida local y pueden variar entre máquinas.
Los tokens siguen la estimación oficial de cuatro caracteres por token.

## Interpretación

- El RAG actual maximiza el resultado conocido, pero pierde 21 consultas
  completas al pasar al holdout.
- El léxico general sacrifica 13 consultas oficiales y recupera 5 consultas
  nuevas respecto del actual.
- El léxico-semántico logró la mejor generalización: 54/60 en el holdout y 6/8
  consultas mult_documento, a costa de más contexto y menor precisión.
- Los embeddings conceptuales ofrecen el mejor equilibrio entre precisión,
  contexto y generalización: 49/60 en el conjunto oficial y 52/60 en el
  holdout, con la mayor precisión del holdout (0,725).
- El híbrido alcanza 53/60 en el holdout, pero emplea más tiempo y contexto que
  el embedding único y conserva menor precisión.
- Las consultas de dos secciones siguen siendo difíciles para el léxico general
  y LSA, que completaron solo 1 de 8. El léxico-semántico mejoró a 6 de 8.

## Limitaciones

- LSA produce embeddings densos locales, pero no es un modelo neuronal
  preentrenado. Su semántica proviene de la coocurrencia dentro de las normas.
- El holdout fue redactado para este trabajo y no reemplaza el test secreto de
  la cátedra.
- Las métricas oficiales evalúan evidencia textual; el holdout evalúa si se
  recuperaron los documentos esperados.
- `entrega.py` continúa apuntando al RAG actual. Las alternativas quedan
  separadas para no cambiar la entrega sin elegir explícitamente una estrategia.

## Reproducción

```powershell
python comparar_rags.py --salida resultados/comparacion_rags.json
python -m unittest -v test_buscador_rag.py test_buscadores_alternativos.py
```
