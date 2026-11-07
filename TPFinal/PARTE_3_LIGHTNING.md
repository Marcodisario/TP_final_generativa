# Parte 3: preparar la optimización del prompt en Lightning AI

## Qué es Lightning

Lightning AI ofrece una computadora en la nube llamada Studio. Podemos preparar archivos en CPU y, al momento de medir, cambiar a una GPU A100 de 40 GB. Es una alternativa a Modal autorizada por la cátedra. No hace falta usar su API de modelos: en este proyecto el modelo se ejecuta localmente dentro del Studio.

Según la [documentación oficial](https://lightning.ai/docs/platform/build/ai-studio), crear una cuenta no requiere tarjeta; puede requerir verificación del teléfono. La [página de precios](https://lightning.ai/pricing) indica 5 créditos de bienvenida y 25 adicionales al agregar tarjeta, mientras que otras partes de la plataforma describen promociones y condiciones diferentes. Confirmar el saldo y la tarifa de A100 de 40 GB en la propia cuenta: las horas anunciadas dependen de la máquina y no equivalen necesariamente a horas de A100. No seleccionar A100 de 80 GB para esta misión.

## Qué quedó preparado

- `entrega.py` conecta el buscador existente con `prompt_gpu/agente.py`. El agente usa el protocolo de herramientas de la cátedra y ejecuta el modelo local, sin consultas a un servicio externo durante los casos.
- Se propone como **línea de base intercambiable**, no como modelo elegido definitivamente, `Qwen/Qwen2.5-7B-Instruct`, revisión `a09a35458c702b33eeacc393d103063234e8bc28`. Su ficha publica 7.615 millones de parámetros y licencia Apache 2.0, y no requiere aprobación de acceso. La referencia de la cátedra usa otro modelo; por eso los resultados no son una comparación idéntica de modelos.
- `prompt_gpu/pyproject.toml` y `prompt_gpu/uv.lock` fijan el entorno GPU separado del kit.
- Esta configuración es para experimentos en Lightning: el `uv sync` de la raíz todavía no instala las dependencias del modelo. Antes de la entrega final hay que integrarlas al entorno reproducible de la cátedra y publicar el checkpoint final.
- `prompt_gpu/preparar_casos.py` generó una partición determinista de los 50 casos de práctica: 30 de **desarrollo** para comparar prompts y 20 de **validación reservada**. El manifiesto y los archivos están en `experimentos/prompt/datos/`. Es una propuesta inicial, no una garantía estadística: el conjunto es pequeño. No usar la validación para elegir o ajustar prompts; el test secreto de la cátedra permanece separado.
- `prompt_gpu/medir_prompt.py` mide exclusivamente el conjunto de desarrollo. Guarda prompt completo y cantidad de tokens, configuración, hashes, salidas y, mediante el kit, las trazas y resultados de cada caso.
- No se entrenó el modelo ni se ejecutó una prueba en GPU. El entorno real de Lightning, el consumo y la compatibilidad de CUDA aún deben verificarse en la primera corrida.

## Antes de usar créditos

1. Crear una cuenta e iniciar un Studio en CPU. [Instrucciones oficiales](https://lightning.ai/docs/platform/overview/getting-started).
2. Llevar el proyecto completo al Studio. Puede clonarse el repositorio **después de guardar y sincronizar los cambios locales**, o subirse la carpeta `TPFinal` por los medios del Studio. Los cambios hechos en esta computadora no aparecen automáticamente en GitHub o Lightning.
3. Abrir la terminal del Studio y entrar a la carpeta `TPFinal`. Los siguientes comandos son para Linux. Si `uv` no está instalado, instalarlo según [su documentación oficial](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync --project prompt_gpu --locked
uv run --project prompt_gpu --locked python -m prompt_gpu.preparar_casos
```

4. Descargar el modelo en CPU antes de la corrida. Es una descarga grande de alrededor de 15 GB; revisar espacio y costo de almacenamiento de la cuenta. El destino debe estar vacío:

```bash
uv run --project prompt_gpu --locked python -m prompt_gpu.preparar_modelo "$HOME/modelos/qwen25-7b-a09a354"
export TP_MODELO_LOCAL="$HOME/modelos/qwen25-7b-a09a354"
```

La descarga usa una revisión fija de Hugging Face. Luego, la evaluación carga los archivos con `local_files_only=True`. No poner tokens ni contraseñas dentro del repositorio.

5. Revisar que `experimentos/prompt/datos/` exista, que haya saldo y que la GPU seleccionada sea una **A100 de 40 GB**. Solo entonces cambiar la máquina a GPU. [Cómo cambiar de GPU](https://lightning.ai/docs/platform/build/ai-studio/add-gpus).

## Primera medición: prompt original

Dentro de `TPFinal`, con A100 de 40 GB y `TP_MODELO_LOCAL` definido:

```bash
nvidia-smi
unset TP_PROMPT
uv run --project prompt_gpu --locked python -m prompt_gpu.medir_prompt --nombre base-original --normas original
```

La corrida usa los 30 casos de desarrollo, el buscador existente, el modelo sin entrenamiento adicional y el mensaje de sistema del agente de ejemplo. El nombre debe ser nuevo; si la corrida falla, sus archivos quedan para auditoría y se usa otro nombre al reintentar.

Los resultados quedan en `experimentos/prompt/corridas/base-original/`: `configuracion.json`, `prompt.txt`, `salida.txt`, `trazas.jsonl`, `tiempos.json`, `resultados.jsonl` y `resumen.json`. `configuracion.json` registra el largo del prompt en tokens sin especiales, la revisión del modelo, la GPU, versiones, hashes y ajustes de generación. El runner guarda lo que entró y salió del modelo y los resultados por caso.

Apagar o poner en reposo el Studio al terminar para detener el cómputo; el almacenamiento puede tener condiciones de cobro propias. [Documentación para detenerlo](https://lightning.ai/docs/platform/build/ai-studio/start-and-stop-studio).

## Comparar otro prompt

Crear un archivo UTF-8 con una variante de instrucciones y ejecutar sobre el mismo conjunto y normas:

```bash
export TP_PROMPT="$PWD/experimentos/prompt/mi-variante.txt"
uv run --project prompt_gpu --locked python -m prompt_gpu.medir_prompt --nombre variante-01 --normas original
```

Comparar `resumen.json`, la cantidad de tokens en `configuracion.json`, tiempo y trazas. Documentar también las variantes que no mejoren. El generador actual procesa las conversaciones **de forma secuencial** para priorizar la primera medición; después se puede estudiar el paralelismo. No usar los 20 casos reservados para decidir variantes; evaluarlos solo después de elegir el prompt. Antes de entrenar, volver a generar las conversaciones con el prompt elegido y fijar los archivos y la configuración de la corrida.
