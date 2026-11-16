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

## Preguntas que te pueden hacer en la defensa

- **¿Por qué validar si el esquema ya le dice al modelo la forma?** Porque el esquema orienta y no garantiza: no sabe si el SOP existe ni puede expresar reglas de negocio entre campos.
- **¿Qué pasa si Claude inventa un SOP?** La validación del catálogo lo rechaza, se le pide corrección y, si insiste, se deriva a QA.
- **¿Cuánto cuesta un reintento?** Lo mismo que una llamada nueva: los tokens se suman.
- **¿Cómo cambiás de modelo?** Se edita `LLM_MODEL` o `LLM_PROVIDER` en `.env`; ningún otro archivo cambia.
- **¿Dónde queda la evidencia?** En `logs/ejecuciones.jsonl`, una línea por evaluación con su `trace_id` y la versión del prompt.
