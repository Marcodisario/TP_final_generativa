# Parte 1 — Fase 1: mapa del historial y las normas

Este documento resume la exploración inicial para preparar la clasificación del historial. No asigna etiquetas ni identifica todavía costumbres. La fuente normativa es `normas/original/`; sus parámetros están en `normas/original/parametros.yaml`.

## 1. Qué hay en el historial

`historial/historial.csv` tiene 2.000 filas, una por admisión, y 28 columnas. Hay 2.000 IDs distintos y 20 operadores. Los valores vacíos deben interpretarse según la columna: por ejemplo, un plazo vacío puede corresponder a que no haya circuito; no siempre indica un error.

| Grupo | Columnas | Qué informan |
|---|---|---|
| Identificación | `id`, `fecha`, `operador` | Identificador, fecha y operador de la admisión. |
| Situación inicial | `edad`, `nivel`, `motivo`, `nota_enfermeria`, `sospecha_sepsis`, `llegada` | Datos del paciente, el triage y cómo llegó. |
| Identidad | `documento_tipo`, `documento_numero` | Tipo y número del documento disponible. |
| Información para consultar | `credenciales`, `puede_responder`, `acompanante`, `lesion_trabajo` | Datos relevantes para identificar la cobertura y a quién preguntar. |
| Cobertura averiguada | `cobertura_declarada`, `art_declarada` | Lo informado sobre obra social/prepaga y ART. |
| Verificación | `entidad_verificada`, `numero_verificado`, `respuesta_verificacion` | A quién y con qué número se verificó, y qué respondió. |
| Ficha registrada | `registro`, `numero_documento`, `box_antes_del_registro`, `circuito`, `plazo_circuito_min`, `cobertura`, `entidad_a_notificar`, `aviso_al_voluntariado` | Las ocho decisiones registradas que deberán contrastarse con normas y costumbres. |

### Algunas observaciones descriptivas

- `nivel` tiene valores de 1 a 5; `llegada` distingue ambulancia y medios propios.
- `documento_tipo` y `documento_numero` están vacíos en 788 filas cada uno. Hay DNI, pasaporte y cédula entre los valores presentes.
- `credenciales` está vacío en 1.222 filas; `acompanante`, en 1.155. `cobertura_declarada` está vacía en 969, pero también existe el valor explícito `ninguna`: vacío y `ninguna` no deben confundirse sin analizar el contexto.
- `entidad_verificada`, `numero_verificado` y `respuesta_verificacion` están vacíos en 413 filas cada uno. Su ausencia no demuestra por sí sola que haya un error: hay que evaluar si correspondía verificar.
- Hay 374 filas con lesión trabajando o en el trayecto, y 374 con `art_declarada` no vacía. Esta coincidencia es descriptiva; no demuestra que los datos ni las decisiones sean correctos.
- `circuito` toma los valores `ecg`, `codigo_acv`, `codigo_sepsis` y `ninguno`. `plazo_circuito_min` está vacío en 608 filas, igual que la cantidad de filas con circuito `ninguno`; hay que comprobar la correspondencia fila por fila antes de asumirla.
- `aviso_al_voluntariado` tiene 339 valores `sí` y 1.661 `no`. Ninguna de las 20 secciones originales menciona voluntariado: esto señala un campo a investigar en el historial, no prueba todavía una costumbre concreta.

## 2. Mapa de normas relevantes para la ficha

Los valores listados son los de las normas **originales**. Las versiones B y C cambian parámetros; el análisis de este historial debe basarse en las normas que le correspondan y comprobar esa premisa antes de clasificar.

| Tema y fuente | Qué dice la norma, resumido | Columnas relevantes | Verificabilidad inicial y cuidados |
|---|---|---|---|
| Registro e identidad: `NOR-ADM-01 §2–3` | Con documento, registro definitivo con su número; sin documento, provisorio. Hay reglas sobre presentación posterior. | `documento_tipo`, `documento_numero`, `registro`, `numero_documento` | Se puede contrastar el estado registrado con el documento consignado, sujeto a la interpretación temporal y a la excepción de `NOR-ADM-03`. El CSV no contiene una secuencia completa de presentación del documento. |
| Excepción de pasaporte/cédula: `NOR-ADM-03` | Con pasaporte o cédula y nivel igual o menor a `P-ADM-3`, registro provisorio con el número del documento. Prevalece sobre ADM-01. | `documento_tipo`, `documento_numero`, `nivel`, `registro`, `numero_documento` | `P-ADM-3 = 2` en original. Aplicar la excepción antes de la regla general y comprobar qué nivel representa la columna del historial. |
| Box antes del registro: `NOR-ADM-01 §4` y `NOR-ADM-02` | Se exige primero box para niveles hasta `P-ADM-1` y también para edad igual o mayor a `P-ADM-2`, cualquiera sea el nivel. | `edad`, `nivel`, `box_antes_del_registro` | En original: `P-ADM-1 = 2`, `P-ADM-2 = 67`. Para los demás, la norma dice que el registro puede hacerse mientras espera; eso no obliga a registrar antes del box. El nivel relevante es el vigente al registrar; el CSV no detalla retriage. |
| Cobertura y consulta: `NOR-COB-01` | Credencial o consulta informan obra social/prepaga; si no puede responder se consulta al acompañante, y si no hay, se considera sin cobertura mientras tanto. Ante lesión laboral se pregunta por ART. | `credenciales`, `puede_responder`, `acompanante`, `cobertura_declarada`, `lesion_trabajo`, `art_declarada` | Los datos permiten inferir parte del contexto, pero el CSV no contiene un registro completo de preguntas ni sus tiempos. Una ausencia no siempre prueba que no se haya preguntado. |
| Verificación y notificación: `NOR-COB-02 §2–5` | Se verifica entidad y número; en lesión laboral se verifica ART usando el CUIL y se notifica a la ART. Si la afiliación ordinaria está activa, se notifica a la entidad, sujeto a excepciones. | `lesion_trabajo`, `credenciales`, `cobertura_declarada`, `art_declarada`, `entidad_verificada`, `numero_verificado`, `respuesta_verificacion`, `entidad_a_notificar` | Hay que extraer nombre y número de campos de texto y respetar la prioridad de ART. Revisar la excepción de COB-04 antes de decidir sobre notificación. El CSV no registra los tiempos ni la secuencia completa. |
| Sin cobertura: `NOR-COB-03` | Incluye falta de cobertura, afiliación inactiva y ciertas situaciones donde no puede informarse; en general no se notifica a una entidad inactiva. ART y COB-04 requieren tratamiento especial. | `puede_responder`, `acompanante`, `cobertura_declarada`, `credenciales`, `respuesta_verificacion`, `lesion_trabajo`, `cobertura`, `entidad_a_notificar` | Diferenciar ausencia de información de declaración `ninguna` y aplicar precedencias. El aviso al Servicio Social no figura como campo de la ficha ni como columna independiente. |
| Terminación reservada: `NOR-COB-04` | Si el número de afiliado de obra social/prepaga termina en `P-COB-2`, se registra sin cobertura y se notifica igual, esté activa o inactiva; se verifica igualmente. No aplica a ART. | `credenciales`, `cobertura_declarada`, `numero_verificado`, `respuesta_verificacion`, `lesion_trabajo`, `cobertura`, `entidad_a_notificar` | En original `P-COB-2 = 7`. La regla se refiere al número informado por credencial o consulta: no asumir que el número verificado es correcto. Precisar cómo interpretar el dígito final y conservar ceros y separadores. |
| Dolor torácico: `NOR-TDE-01` | Si el motivo es dolor torácico, corresponde ECG en el plazo `P-TDE-1`; no se activa por otro motivo. | `motivo`, `circuito`, `plazo_circuito_min`, `llegada` | En original `P-TDE-1 = 10` minutos. Aplicar el ajuste por ambulancia. La ficha registra un plazo; no permite por sí sola verificar la hora real de realización. |
| ACV: `NOR-TDE-02` | Para signos neurológicos focales súbitos corresponde código ACV con plazo `P-TDE-2`. La norma también pide informar hora de inicio o última vez visto bien. | `motivo`, `circuito`, `plazo_circuito_min`, `llegada`, `nota_enfermeria` | En original `P-TDE-2 = 10` minutos. Aplicar el ajuste por ambulancia. El CSV no muestra toda la secuencia de preguntas o comunicación. |
| Sepsis: `NOR-TDE-03` | Ante sospecha de sepsis, código sepsis; probable o con shock usa `P-TDE-3`, posible sin shock usa `P-TDE-4`. Sin sospecha no se activa. | `sospecha_sepsis`, `circuito`, `plazo_circuito_min`, `llegada` | En original, plazos 15 y 60 minutos respectivamente. Usar la categoría consignada y aplicar el ajuste por ambulancia. |
| Ambulancia: `NOR-TDE-04` | Si corresponde un circuito y llegó en ambulancia, se resta `P-TDE-5` al plazo. | `llegada`, `circuito`, `plazo_circuito_min`, más datos del circuito esperado | En original `P-TDE-5 = 5` minutos. Determinar primero el circuito que corresponde según el triage; no confiar ciegamente en el circuito registrado. |

## 3. Normas que no se pueden clasificar directamente con esta ficha

`NOR-DER-01`, `NOR-GUA-01` a `03` y `NOR-INT-01` a `05` tratan derivación, evaluación médica, tipo de box, retriage y camas de internación. Pueden aportar contexto, pero la ficha de ocho campos y este CSV no registran, en general, la secuencia de eventos, disponibilidad de camas, indicaciones médicas o tiempos necesarios para verificar esas normas completas. No convertir la falta de esos datos en una infracción.

Otras disposiciones de las normas de admisión y cobertura regulan tiempos, preguntas, avisos al Servicio Social o presentación posterior de información. Se debe evaluar en cada caso si el historial conserva evidencia suficiente; no asumir que podemos auditar toda una admisión a partir de la ficha final.

## 4. Criterios y preguntas para la próxima fase

1. Confirmar qué versión de normas corresponde al historial y cómo interpretar el momento del `nivel` y los campos de documento.
2. Para cada regla, especificar condiciones, excepciones, precedencia y columnas necesarias, citando norma y sección.
3. Distinguir internamente `violación`, `compatible` e `información insuficiente`. Las etiquetas finales permitidas siguen siendo `correcta`, `error` y `ruido`.
4. Investigar las costumbres solo donde las normas no deciden el resultado, comparando casos realmente similares y respaldando las conclusiones con IDs.
5. Tratar nombres y números de afiliación como texto: pueden tener guiones, barras y ceros. La entidad y número que se debían verificar deben inferirse de los datos de origen, no de lo que el operador efectivamente verificó.
6. No asumir que una mayoría o la ausencia de una norma prueban automáticamente una costumbre. Revisar grupos, diferencias y evidencia antes de clasificar ruido.

Este mapa es un punto de partida. Debe revisarse contra las normas completas y los datos al implementar cada regla; aún no es un clasificador ni un resultado de la cátedra.
