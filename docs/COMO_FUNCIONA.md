# Cómo funciona el motor (explicado sin saber programar)

## La idea en una frase

El motor es un **analista junior muy rápido** (el modelo de lenguaje) que propone evaluaciones de impacto, rodeado de **controles de calidad automáticos** (Pydantic) que revisan cada propuesta antes de que llegue a QA. El junior propone; los controles rechazan lo que no cumple; QA decide.

Si lo pensás como un proceso GxP:

| Pieza del sistema | Equivalente en tu mundo |
| --- | --- |
| `src/contrato.py` | El **formulario controlado** con sus campos obligatorios y sus listas cerradas |
| `prompts/sistema.md` | El **SOP** que lee el analista antes de evaluar |
| `prompts/usuario.md` | La **carátula del CCAM** que recibe el analista |
| `config/catalogo_sops.json` | El **listado maestro de documentos vigentes** |
| `src/proveedores.py` | El **teléfono** con el que se llama al analista (Claude u otro) |
| `src/motor.py` | El **circuito del CCAM**: quién recibe, quién revisa, qué pasa si está mal |
| `logs/ejecuciones.jsonl` | El **audit trail**: una línea por cada evaluación |
| `scripts/corrida.py` | La **corrida de calificación**: los 15 casos y los errores, con manifiesto y hashes, como un protocolo ejecutado |
| `tests/` | Los **casos de prueba** del OQ, que se pueden repetir sin costo |

## El recorrido de un CCAM, paso a paso

Usamos el ejemplo `consultas/01_version_software.json`: actualizar el software cromatográfico de la versión 3.6 a la 3.8.

### Paso 0. Alguien lo pide

Escribís en la terminal:

```
python -m src.motor consultas/01_version_software.json
```

Eso significa: "ejecutá el archivo `src/motor.py` y pasale este CCAM". El motor lee el archivo y saca la parte `entrada`.

### Paso 1. Control de la entrada (`contrato.py` → clase `Entrada`)

Antes de gastar un centavo, se revisa el pedido:

- ¿El `id_ccam` tiene el formato `CCAM-2026-101`? (patrón)
- ¿El `tipo_cambio` es uno de la lista? (Enum)
- ¿La descripción tiene al menos 30 caracteres? (largo mínimo)

**Si algo falla, el recorrido termina acá** con un error `entrada_invalida` que dice qué campo está mal. No se llama al modelo, así que no cuesta nada. Es el mismo criterio que rechazar un formulario incompleto en mesa de entradas.

### Paso 2. Armado del pedido al modelo (`motor.py` → `armar_prompts`)

Se llenan dos plantillas:

- **Sistema** (`prompts/sistema.md`): el rol, los criterios para clasificar el impacto, el catálogo de SOPs que puede citar y las reglas. Es igual para todos los CCAM.
- **Caso** (`prompts/usuario.md`): los datos de *este* CCAM, insertados en los huecos `$id_ccam`, `$descripcion`, etc.

Además se calcula la **versión del prompt**: una huella de 12 caracteres de las plantillas y el catálogo. Si alguien cambia una coma del SOP del modelo, la huella cambia, y en el log queda qué versión generó cada propuesta. Es control de versiones documental.

### Paso 3. La llamada (`proveedores.py` → `ProveedorAnthropic.generar`)

El motor no sabe hablar con Claude: le pide al proveedor "generá una propuesta". El proveedor arma la llamada:

| Lo que se manda | Para qué |
| --- | --- |
| `model` | Qué modelo (sale de `.env`, por ejemplo `claude-haiku-5-5`) |
| `system` | El SOP del modelo (paso 2) |
| `messages` | El CCAM concreto |
| `tools` + `tool_choice` | La **forma obligatoria** de la respuesta: el esquema de la clase `Salida` |
| `max_tokens` | El techo de largo de la respuesta |

La clave de la API **no está en el código**: la librería la lee de la variable `ANTHROPIC_API_KEY` del archivo `.env`, que nunca se sube a GitHub.

Claude responde con: la propuesta (todavía sin revisar) y el campo `usage`, que dice cuántos tokens leyó y cuántos escribió.

**Si la API falla** (sin conexión, límite de uso, clave inválida), el proveedor lo traduce a un error con nombre claro (`api_sin_conexion`, `api_limite_uso`, `api_autenticacion`) y el motor devuelve un error estructurado.

### Paso 4. Control de la salida (`contrato.py` → clase `Salida`)

Esta es la parte central. La propuesta pasa por tres niveles de control:

1. **Campos:** ¿el impacto es uno de los 4 valores? ¿La confianza está entre 0 y 1? ¿El código de SOP tiene el formato correcto?
2. **Catálogo:** ¿el SOP citado **existe** en el listado maestro? Si Claude inventa un `SOP-QA-099`, se rechaza.
3. **Reglas cruzadas:** ¿un impacto mayor tiene al menos una tarea? ¿Una revalidación con "sin impacto"? Combinaciones que no tienen sentido de negocio.

**Si pasa**, sigue al paso 5.

**Si no pasa**, el motor:

1. Anota **qué campo falló**, por ejemplo `fundamento -> 0 -> codigo: SOP-QA-099 no existe en el catálogo`.
2. Le devuelve ese error a Claude con la plantilla `prompts/correccion.md`: "tu propuesta no cumple el contrato, corregí esto".
3. Hace **un** reintento. Si ahora pasa, sigue. Si vuelve a fallar, devuelve el error estructurado `salida_invalida` con la acción "Derivar a QA para evaluación manual".

Es exactamente un circuito de corrección de documentos: se devuelve al autor con la observación, y si vuelve mal, escala.

### Paso 5. Medición (`motor.py` → `calcular_costo`)

- **Tokens:** se suman los de **todos** los intentos (un reintento se paga).
- **Costo:** tokens × precio de `config/precios.json` ÷ 1 millón.
- **Latencia:** cronómetro desde antes de la primera llamada hasta el final, en milisegundos.

### Paso 6. Registro (`motor.py` → `_cerrar`)

Se agrega una línea a `logs/ejecuciones.jsonl` con: fecha UTC, `trace_id` (identificador único de esta ejecución), id del CCAM, versión del prompt, resultado, impacto propuesto, campos que fallaron, tokens, costo y latencia. **No se guarda la descripción del CCAM**: solo metadatos, para no duplicar información sensible.

## Los cuatro finales posibles

| Final | Cuándo | Qué devuelve | ¿Gasta tokens? |
| --- | --- | --- | --- |
| Propuesta válida | Todo bien, al primer o segundo intento | `ok: true` + propuesta + métricas | Sí |
| `entrada_invalida` | El pedido no cumple el contrato | Campos mal cargados | No |
| `salida_invalida` | Claude falló dos veces el contrato | Campos que fallaron + "derivar a QA" | Sí, los dos intentos |
| `api_...` | Problema de conexión, límite o clave | Tipo de error + mensaje | Lo consumido hasta ahí |

## Cómo leer lo que imprime la terminal

```
WARNING [3838c73758ea] intento 1/2: salida inválida -> fundamento -> 0 -> codigo: ...
```

- `WARNING`: aviso, no es fatal todavía.
- `[3838c73758ea]`: el `trace_id`. Con ese código encontrás la línea en el log.
- `intento 1/2`: primer intento de dos posibles.
- `fundamento -> 0 -> codigo`: la ruta del campo. "En la lista `fundamento`, el elemento 0 (el primero), el campo `codigo`".

La última línea resume:

```
VALIDADO | modelo claude-haiku-5-5 | intentos 1 | tokens 1196/320 | USD 0.000280 | 2400 ms | trace 1a2b3c4d5e6f
```

## Glosario mínimo

| Término | Qué es |
| --- | --- |
| **Pydantic** | Librería que define formularios (clases) y rechaza datos que no cumplen |
| **Enum** | Lista cerrada de valores permitidos |
| **Patrón (regex)** | Regla de formato, como `CCAM-` + 4 dígitos + `-` + 3 o 4 dígitos |
| **Regla cruzada** | Control que mira varios campos juntos (`@model_validator`) |
| **Prompt** | El texto que se le manda al modelo |
| **Token** | Unidad en la que el modelo lee, escribe y cobra (≈ ¾ de palabra) |
| **API** | La "ventanilla" de Anthropic a la que el programa le hace pedidos por internet |
| **Proveedor** | Quién atiende esa ventanilla: Anthropic, OpenAI o el simulador |
| **Simulador** | Un proveedor falso que responde siempre lo mismo; sirve para probar sin pagar |
| **trace_id** | Identificador único de una ejecución, para rastrearla |
| **`.env`** | Archivo local con la clave y la configuración; nunca se sube |

## Por qué no hay temperatura

En clase se vio que la temperatura controla la variabilidad y que para clasificar conviene 0. Pero desde la versión 2026-10-21 de su API, **Claude ya no acepta ese parámetro**: siempre responde con su variabilidad por defecto. Por eso, en este sistema la consistencia no depende de una perilla del modelo, sino de controles propios: el contrato, el catálogo cerrado de SOPs, el reintento con corrección y, en la PE6, la medición de cuán estable es la clasificación cuando se repite el mismo caso. Es el principio GxP de siempre: no confiar en que el proceso salga bien, verificarlo.

## Cómo encuentra los documentos (PE3)

En la PE2 el modelo solo veía una lista con el código y el título de 7 SOPs. Desde la PE3 lee **los documentos del laboratorio**, y solo los que la persona que pregunta tiene permitido leer. Es la diferencia entre evaluar un cambio de memoria y hacerlo con el procedimiento abierto sobre la mesa.

### Las piezas, en criollo

| Pieza | Qué es | Equivalente GxP |
| --- | --- | --- |
| **Corpus** (`documentos/`) | 10 documentos ficticios en Markdown, cada uno con carátula: código, versión, vigencia y roles que lo pueden leer | La lista maestra de documentos controlados |
| **Fragmento** | Un pedazo de documento de ~400 tokens (unas 250 palabras), cortado por secciones, que arranca con su etiqueta: `SOP-VS-002 · Validación... · §6.3 ...` | Citar "SOP-VS-002 §6.3" en vez de "el SOP de validación" |
| **Ingesta** (`python -m src.rag.ingestar`) | Un solo comando lee todo, corta, calcula y guarda; deja un manifiesto con el hash SHA-256 de cada documento | La carga controlada al sistema documental, con registro de qué versión quedó |
| **Embedding** | Una lista de 384 números que representa el *significado* de un texto. Textos parecidos tienen números parecidos | No tiene; es la forma de que la máquina encuentre "por tema" |
| **Búsqueda vectorial** | Busca los fragmentos con significado más parecido a la pregunta | Preguntarle a un colega "¿dónde habla de mudar una cámara?" |
| **BM25** | Busca por coincidencia de palabras exactas, premiando las palabras raras | Ctrl+F en el sistema documental: encuentra `HPLC-QC-03` y no lo confunde con `HPLC-QC-04` |
| **RRF** | Junta los dos rankings: puntaje = suma de 1/(60 + puesto) en cada lista | Dos revisores ordenan por separado y se queda lo que ambos ponen arriba |
| **Pre-filtro por rol** | La búsqueda se hace **solo** sobre lo que el rol puede leer; lo demás ni se mira | Control de accesos por perfil: el archivo restringido no aparece en tu listado |
| **requiere_humano** | Si los documentos no alcanzan para responder, el sistema no clasifica y lo deriva a QA | "No tengo procedimiento para esto: lo decide QA" |

### El recorrido de un CCAM con RAG (`responder`)

1. Valida la Entrada (igual que la PE2).
2. Resuelve quién pregunta con `config/usuarios.json`. Lo resuelve el código, nunca el modelo. Si el usuario no existe: `acceso_denegado`, sin buscar.
3. Busca dos veces con los permisos de ese usuario: con el texto del CCAM y con la matriz de clasificación de SOP-CC-001 (es el criterio, se trae siempre).
4. Si nada se parece ni de lejos (similitud menor a 0,20), responde `requiere_humano` sin llamar al modelo.
5. Le pasa al modelo los fragmentos encontrados, cada uno con su código y sección, en lugar del catálogo.
6. Valida la respuesta: **cada cita tiene que estar entre los fragmentos que se recuperaron en esa misma llamada**. Una cita que no se recuperó es una cita inventada y se rechaza. Si una tarea nombra un SOP, ese SOP tiene que estar en el fundamento (regla H-02).
7. Deja rastro: usuario, rol, fragmentos usados y versión del prompt, sin el texto del CCAM.

### Cómo se cuenta un acierto (definición formal, devolución PE3 M-2)

- **Pregunta con respuesta:** Acierto@k = 1 si entre los k primeros fragmentos hay uno del documento esperado que contiene la sección esperada.
- **Pregunta sin respuesta o restringida:** Acierto@k = 1 si ninguno de los k primeros fragmentos es de un documento que el rol no puede leer (y, en las restringidas, ninguno es del documento restringido).
- **Respuesta correcta:** normal → `requiere_humano = false` y cita del documento esperado; sin respuesta o restringida → `requiere_humano = true`, sin citas y sin el restringido en `fuentes`.
- Recall@k = aciertos / preguntas del grupo. La definición vive también en `evals/preguntas_pe3.json`.

### `fuentes` no es lo mismo que `fundamento` (devolución PE3 M-3)

| Campo | Qué es | Quién lo produce |
| --- | --- | --- |
| `fuentes` | Los fragmentos que el sistema **recuperó y le mostró** al modelo, con documento, secciones, versión, hash del documento, puntaje RRF y similitud | El buscador, con los permisos del rol |
| `propuesta.fundamento` | Lo que el modelo **cita** para justificar la clasificación | El modelo, validado contra `fuentes` |

Toda cita del fundamento tiene que estar entre las fuentes; no toda fuente termina citada. El objeto de `responder()` lleva además `trace_id`, `usuario`, `rol`, `version_prompt`, `configuracion_fragmentos`, `modelo_embeddings`, `timestamp_utc` y las métricas.

### Por qué BM25 tiene que respetar los permisos

Si BM25 se armara con todo el corpus y después se filtrara, el puntaje de los fragmentos visibles cambiaría según lo que hay en los invisibles: alguien atento podría deducir que existe un documento restringido sobre el tema. Por eso el índice de palabras se arma cada vez **solo con lo autorizado**. Es la diferencia entre no mostrar un expediente y no tenerlo en el cajón.

### Cómo se prueba que un restringido no se filtra

Cada documento restringido tiene una **frase testigo** única (por ejemplo `TESTIGO-INSP-2290`). La prueba pregunta por esa frase con cada usuario y verifica dos cosas: que no aparece en los resultados y que **no aparece en el texto que se le manda al modelo** (el simulador guarda una copia de ese texto). Como control, el jefe de QA sí la recibe: si no, la prueba pasaría por casualidad.

### Preguntas que te pueden hacer sobre la PE3

- **¿Por qué no filtrar después de buscar?** Porque lo que se buscó ya pasó por la memoria del programa y por los puntajes; el control tiene que estar antes, como el perfil de acceso.
- **¿Por qué híbrida y no solo vectorial?** Porque los códigos (`CAPA-2026-014` frente a `CAPA-2026-041`) son casi iguales en significado y distintos en lo que importa. En la corrida, la vectorial falló en 4 de 14 consultas donde la híbrida acertó.
- **¿Por qué fragmentos de 400 y no de 1.000 tokens?** Con este corpus las dos aciertan igual con la híbrida, pero la de 400 manda la mitad de texto al modelo y permite citar la sección exacta.
- **¿Por qué ChromaDB y no Pinecone?** ChromaDB corre en la máquina: los documentos GxP no salen a un tercero. Pinecone convendría con varias plantas, miles de documentos y muchos usuarios a la vez, si la evaluación de proveedor y la residencia de datos lo permiten.

## Cómo actúa con permiso (PE4)

Hasta la PE3 el sistema respondía. Desde la PE4 también **hace cosas** en el sistema de gestión de cambios: consulta CCAM y registra borradores de evaluación. Lo hace un **agente**: un programa que en cada paso decide qué hacer, en vez de seguir un camino fijo. Antes de escribir, se frena y espera la firma de QA.

### Las piezas

| Pieza | Qué es | Equivalente GxP |
| --- | --- | --- |
| **Sistema simulado** (`src/sistema.py`) | Una base SQLite con los 15 CCAM ficticios, sus estados, los borradores registrados y una tabla de auditoría | El sistema de gestión de cambios de la planta, en versión de prueba |
| **Servidor MCP** (`src/mcp_servidor.py`) | Un programa aparte que expone el sistema con 3 herramientas tipadas: `consultar_ccam` y `listar_ccam` (lectura), `registrar_evaluacion` (escritura) | La interfaz validada: qué se puede hacer y con qué datos, y nada más |
| **Grafo** (`src/agente/grafo.py`) | El camino del agente dibujado como nodos y flechas: decidir, ejecutar, pedir aprobación, responder | El diagrama de flujo del procedimiento |
| **Estado** | La pizarra que viaja entre nodos: mensajes, usuario, pasos, `pendiente_aprobacion` | El expediente con sus fojas |
| **interrupt** | La pausa antes de escribir: muestra qué va a hacer y con qué datos | El borrador sobre el escritorio del aprobador |
| **Checkpointer** | Guarda una foto del estado después de cada paso, por `thread_id` | El expediente archivado: se retoma donde quedó, aunque sea otro día |
| **Límite de pasos** | Si el agente no termina en 6 pasos, el sistema lo corta y avisa | El plazo del procedimiento: si no se resuelve, escala |

### Quién aprueba

Aprueba **QA formal** (`u_jefe_qa`), y **nunca quien pidió la escritura**. Se controla dos veces: en el agente (si no se cumple, la aprobación cuenta como rechazo) y en el servidor MCP (si alguien lo llamara directo, igual rechaza). Registrar el borrador **no aprueba el cambio**: queda `BORRADOR_PENDIENTE_QA`.

### Lo que el modelo no puede hacer

- Inventar una acción: elige de una lista cerrada (`Decision`).
- Inventar la clasificación que se escribe: solo dice qué CCAM; lo que se registra es lo que validó el motor en esa conversación.
- Escribir sin firma: el nodo que ejecuta vuelve a comprobar que la aprobación existe.
- Saltarse el límite: no sabe cuántos pasos tiene; el corte lo hace el código.

### Cómo usarlo

```bash
python -m scripts.agente --usuario u_analista_qa --thread ccam-101 "Evaluá el CCAM-2026-101 y registrá el borrador"
python -m scripts.agente --thread ccam-101 --aprobar u_jefe_qa        # o --rechazar u_jefe_qa --motivo "..."
python -m scripts.agente --thread ccam-101 --estado
python -m scripts.cliente_mcp                                          # prueba el servidor solo
python -m scripts.corrida_pe4                                          # las 5 conversaciones de la entrega
```

## Preguntas que te pueden hacer en la defensa

- **¿Por qué validar si el esquema ya le dice al modelo la forma?** Porque el esquema orienta y no garantiza: no sabe si el SOP existe ni puede expresar reglas de negocio entre campos.
- **¿Qué pasa si Claude inventa un SOP?** La validación del catálogo lo rechaza, se le pide corrección y, si insiste, se deriva a QA.
- **¿Cuánto cuesta un reintento?** Lo mismo que una llamada nueva: los tokens se suman.
- **¿Cómo cambiás de modelo?** Se edita `LLM_MODEL` o `LLM_PROVIDER` en `.env`; ningún otro archivo cambia.
- **¿Dónde queda la evidencia?** En `logs/ejecuciones.jsonl`, una línea por evaluación con su `trace_id` y la versión del prompt.
