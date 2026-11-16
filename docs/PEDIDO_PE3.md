# Pedido: Pre-Entrega 3, RAG con permisos y búsqueda híbrida

Pedido para Claude Code, escrito desde la app de Claude el 2026-11-02. Leer antes `CLAUDE.md`, `docs/ESTADO.md`, `docs/DECISIONES.md` y `docs/COMO_FUNCIONA.md`.

**Orden:** empezar recién cuando `docs/PEDIDO_CORRECCIONES_PE2.md` esté cerrado (tag `pe2`, `scripts.corrida`, CI en verde y los 10 casos nuevos). Esta entrega usa esa misma base de evidencia.

## 1. Qué pide la consigna

El motor de la PE2 respondía con lo que sabe el modelo y un catálogo cerrado de SOPs en el prompt. Ahora tiene que responder **con los documentos del laboratorio**, recuperados de forma híbrida y **filtrados por rol antes de buscar**, citando siempre la fuente.

### Rúbrica (100 puntos, aprueba con 70)

| Criterio | Peso | Qué tiene que mostrar el PDF |
| --- | --- | --- |
| Permisos antes de buscar | 25 % | Filtro por rol en la consulta a la base, no después. Un test por rol. Un test que prueba que un usuario sin permiso no recibe nada de un documento restringido, **ni en los resultados ni en el prompt enviado al modelo** |
| Búsqueda híbrida con evidencia | 20 % | Vectorial + BM25 fusionados con RRF. Al menos **2 consultas donde la híbrida acierta y la solo vectorial falla** (códigos exactos) |
| Ingesta y metadatos | 15 % | Un solo comando procesa los documentos. Cada fragmento lleva documento, sección y roles que pueden leerlo |
| Respuesta con fuentes | 15 % | Responde solo con lo recuperado y cita el documento. Sin evidencia suficiente: `requiere_humano = true` en lugar de inventar |
| Preguntas y medición | 15 % | Archivo con 10 preguntas (6 normales, 2 sin respuesta, 2 sobre documentos restringidos), cada una con su documento esperado. Recall@k con **dos configuraciones de fragmentado** y cuál ganó |
| Decisiones | 10 % | Tamaño de fragmento elegido y por qué; en qué situación del cliente convendría Pinecone en vez de ChromaDB |

### Contrato de las piezas (obligatorio, con estos nombres)

- `ingestar(carpeta)` → colección en ChromaDB.
- `buscar(consulta, usuario, k)` → lista de fragmentos con `documento`, `fragmento_id`, `texto` y `puntaje`.
- `responder(entrada)` → recibe la `Entrada` de la PE2 y devuelve la `Salida` más una lista de `fuentes`.

## 2. Roles y usuarios

Salen del requisito 5 de la PE1 ("solo los involucrados ven un CCAM; quien abre no aprueba") y de la segregación de funciones. **Ficticios**, en `config/usuarios.json`:

| Rol | Usuario de prueba | Puede leer |
| --- | --- | --- |
| `solicitante` | `u_solicitante_prod` (Producción) | SOPs e instructivos vigentes |
| `analista_qa` | `u_analista_qa` | SOPs + informes de auditoría interna |
| `validaciones` | `u_validaciones` | SOPs + expedientes de validación |
| `jefe_qa` | `u_jefe_qa` | Todo, incluidos los hallazgos de inspección |

La identidad la resuelve el código a partir de `usuarios.json`, nunca el modelo. Un usuario o rol desconocido no recibe nada y se registra como `acceso_denegado`.

## 3. Corpus de documentos (ficticio)

Carpeta `documentos/`, en Markdown, con secciones numeradas (`## 5.2 ...`) para que las citas sean del tipo `SOP-VS-002 §6.3`. Cada documento empieza con un encabezado YAML con `codigo`, `titulo`, `version`, `vigente_desde` y `roles_lectura`.

| Código | Documento | Roles de lectura | Para qué sirve en la prueba |
| --- | --- | --- | --- |
| SOP-CC-001 | Gestión de control de cambios, con la **matriz de clasificación de impacto** | todos | Fuente principal de la clasificación |
| SOP-VS-002 | Validación de sistemas computarizados (GAMP 5) | todos | Revalidación por cambio de software |
| SOP-VS-003 | Evaluación de riesgo e integridad de datos (ALCOA+, Part 11, Anexo 11) | todos | Audit trail, firmas electrónicas |
| SOP-DC-004 | Gestión documental | todos | Cambios documentales menores |
| SOP-EQ-005 | Calificación de equipos e instalaciones | todos | Recalificación, mapeo de cámaras |
| SOP-PR-006 | Calificación de proveedores | todos | Cambio de proveedor |
| SOP-AC-007 | Material de empaque y rotulado | todos | Packaging |
| INF-AUD-2026-03 | Informe de auditoría interna de control de cambios | `analista_qa`, `jefe_qa` | **Restringido** |
| EXP-VAL-CROM-01 | Expediente de validación del software cromatográfico, equipos HPLC-QC-01 a 04 | `validaciones`, `jefe_qa` | **Restringido**; códigos exactos de equipo |
| HAL-INSP-2026-01 | Hallazgos de inspección y plan de acciones | `jefe_qa` | **Restringido**, el más sensible |

Reglas para el corpus:

- **Claude Code redacta los borradores; Federico revisa** SOP-CC-001 antes de la corrida, porque es su criterio de QA.
- La matriz de SOP-CC-001 (sección 5) define cada nivel de impacto e incorpora como **ejemplos los 10 casos clasificados** del pedido de correcciones, con la frase "por qué ese nivel y no el vecino". Es la respuesta de fondo al hallazgo H-01.
- SOP-CC-001 incluye la regla R-QA-01: ante la duda real, el nivel más alto, pidiendo el dato que falta.
- Los documentos restringidos contienen **frases testigo** únicas (por ejemplo `TESTIGO-AUD-7731`) para poder probar que nunca llegan a un usuario sin permiso ni al prompt.
- Incluir códigos exactos que la búsqueda vectorial confunda entre sí (`HPLC-QC-03` frente a `HPLC-QC-04`, `SOP-VS-002` frente a `SOP-VS-003`, `CAPA-2026-014` frente a `CAPA-2026-041`). Son el material de la evidencia de búsqueda híbrida.

## 4. Diseño técnico

### Ingesta (`python -m src.rag.ingestar`)

- Un solo comando: lee `documentos/`, limpia, fragmenta, calcula embeddings y guarda en ChromaDB persistente (`.chroma/`, en `.gitignore`).
- **Fragmentado estructural por secciones** (recursivo con separadores de título, párrafo y línea) con **~10 % de solapamiento**, como baseline de la clase.
- **Contextual retrieval:** cada fragmento se indexa con un prefijo verificable, sin inventar nada: `SOP-VS-002 · Validación de sistemas computarizados · §6.3 Revalidación por cambio de versión`.
- **Metadatos por fragmento:** `documento`, `titulo`, `seccion`, `version`, `fragmento_id`, `chunk_index`, `hash_documento` (SHA-256 del archivo fuente) y un booleano por rol (`rol_solicitante`, `rol_analista_qa`, `rol_validaciones`, `rol_jefe_qa`), para que el filtro sea un `where` simple de ChromaDB.
- **Embeddings:** un modelo multilingüe local y gratuito, por ejemplo `intfloat/multilingual-e5-small` con `sentence-transformers`. El de por defecto de ChromaDB está entrenado en inglés y el corpus es en español. No usar embeddings pagos: el presupuesto es el crédito de USD 10 de Anthropic, que no ofrece embeddings. Verificar el nombre del modelo y su licencia antes de fijarlo.
- La ingesta registra en `resultados/` un manifiesto con la cantidad de fragmentos por documento, la configuración de fragmentado y los hashes.

### Búsqueda (`buscar(consulta, usuario, k)`)

1. Resolver el usuario y sus roles desde `config/usuarios.json`. Si no existe: lista vacía y registro `acceso_denegado`.
2. **Pre-filtrado:** la consulta vectorial a ChromaDB lleva `where={"rol_<rol>": True}`.
3. **BM25 sobre el subconjunto autorizado:** el índice léxico se arma o filtra **solo con los fragmentos que ese rol puede leer**, nunca sobre el corpus completo (si no, los puntajes filtran información y se rompe el pre-filtrado). Biblioteca sugerida: `rank-bm25`, con una tokenización que conserve los códigos con guiones (`SOP-VS-002` es un solo término).
4. **Fusión RRF** con k = 60: `puntaje = Σ 1 / (60 + rango)`.
5. Devolver los top-k con `documento`, `fragmento_id`, `texto`, `seccion` y `puntaje`.
6. Dejar también `buscar_vectorial()` y `buscar_bm25()` por separado: la medición los compara con la híbrida.

### Respuesta (`responder(entrada)`)

- Arma la consulta de búsqueda a partir de la `Entrada` (tipo de cambio, sistema afectado y descripción) y recupera con el usuario que hace el pedido.
- **Reemplaza el catálogo cerrado del prompt** por los fragmentos recuperados, cada uno con su código y sección.
- El validador de `fundamento` pasa a exigir que cada SOP citado **esté entre las fuentes recuperadas en esta llamada**, no solo en el catálogo. Una cita que no se recuperó es una cita inventada.
- **Regla cruzada nueva (hallazgo H-02):** todo código de SOP mencionado en el texto de una tarea debe figurar en `fundamento`.
- **Sin evidencia suficiente** (ningún fragmento por encima de un umbral, o el modelo indica que no alcanza): `requiere_humano = true`, sin clasificar. El umbral se fija con las preguntas de prueba y queda en `config/`.
- `Salida` suma `requiere_humano: bool` y la respuesta suma `fuentes: list[Fuente]` con `documento`, `seccion`, `fragmento_id` y `puntaje`.
- Se agrega R-QA-01 al prompt de sistema y la `version_prompt` cambia: queda registrado en la medición.

### Decisión pendiente de Federico (O-1)

En el caso 08, QA rechazaría el cambio y el contrato no tiene cómo expresarlo. Si Federico lo aprueba, `Salida` suma `recomendacion: proceder | proceder_con_condiciones | no_proceder`, con la regla cruzada `no_proceder ⇒ impacto critico`. **No implementarlo hasta que lo confirme** en `docs/DECISIONES.md`.

## 5. Preguntas de prueba

`evals/preguntas_pe3.json`: 10 preguntas en lenguaje natural para medir la recuperación, cada una con `usuario`, `documento_esperado` y `seccion_esperada` (o `null`).

| Tipo | Cantidad | Qué tienen que mostrar |
| --- | --- | --- |
| Normales | 6 | Al menos 2 con **código exacto** (por ejemplo "¿qué recalificación pide el HPLC-QC-03?", "¿qué dice el SOP-VS-003 sobre desactivar el audit trail?") y 4 en lenguaje natural sin códigos |
| Sin respuesta | 2 | Algo que ningún documento cubre (por ejemplo, el plazo de pago a proveedores): esperado `requiere_humano = true` |
| Restringidas | 2 | Hechas por un usuario **sin** permiso sobre el documento que tiene la respuesta (por ejemplo, `solicitante` preguntando por los hallazgos de inspección): esperado lista vacía de ese documento y `requiere_humano = true` |

Federico revisa las 10 preguntas y sus documentos esperados antes de la corrida.

## 6. Medición

`python -m scripts.corrida_pe3`, con el mismo patrón de una sola corrida de la PE2 (carpeta `resultados/corrida_pe3_AAAAMMDD_HHMM/`, archivos completos, manifiesto con hashes):

1. **Recall@k** (k = 3 y k = 5) de las 10 preguntas para vectorial, BM25 e híbrida.
2. Con **dos configuraciones de fragmentado**: A, fragmentos chicos de ~400 tokens; B, fragmentos de ~1.000 tokens; las dos con ~10 % de solapamiento y corte estructural. Reportar cuál ganó y por qué.
3. Tabla de las consultas donde **la híbrida acierta y la vectorial falla**: tienen que ser al menos 2.
4. Las 15 consultas CCAM de `consultas/` corridas por `responder()` con el usuario `u_analista_qa`: coincidencia con QA total, por grupo y por nivel, comparada con la corrida de la PE2. Cuánto cambió por pasar del catálogo al RAG y a la matriz de SOP-CC-001.
5. Tokens, costo y latencia por consulta: el prompt crece con los fragmentos.

## 7. Pruebas (sin gastar tokens)

- **Una prueba de permisos por rol** (`solicitante`, `analista_qa`, `validaciones`, `jefe_qa`): cada uno recupera lo que le corresponde y nada más.
- **La prueba clave de la rúbrica:** un `solicitante` pregunta por la frase testigo de `HAL-INSP-2026-01`. No aparece en los resultados de `buscar()` y **no aparece en el prompt** que `responder()` le envía al modelo. El prompt se captura con el proveedor simulado.
- Un usuario desconocido no recibe nada.
- BM25 no puntúa fragmentos no autorizados.
- RRF ordena bien un caso calculado a mano (el ejemplo de la clase: A en posiciones 1 y 3, B en 2 y 1, k = 60, gana B).
- `fundamento` rechaza un SOP que no está entre las fuentes recuperadas.
- La regla H-02 rechaza un SOP en una tarea que no está en el fundamento.
- Sin evidencia: `requiere_humano = true`.
- Siguen en verde todas las pruebas de la PE2, en la CI.

## 8. Documentación

- `docs/COMO_FUNCIONA.md`: capítulo nuevo "Cómo encuentra los documentos", en criollo: fragmento, embedding, BM25, RRF y pre-filtrado, con el equivalente GxP (lista maestra, control de acceso por perfil, segregación de funciones).
- `docs/DECISIONES.md`: tamaño de fragmento (con el resultado de la medición), modelo de embeddings, ChromaDB frente a Pinecone, BM25 sobre el subconjunto autorizado y validación de citas contra las fuentes recuperadas.
- **ChromaDB frente a Pinecone**, para la sección de decisiones del PDF: ChromaDB alcanza con este corpus (decenas de documentos, una planta, sin alta concurrencia) y corre local, sin enviar documentos GxP a un tercero. Pinecone convendría si el laboratorio unificara varias plantas y miles de documentos con muchos usuarios simultáneos y alta disponibilidad, siempre que la evaluación de proveedor y la residencia de datos lo permitan.
- `docs/ESTADO.md` y bitácora actualizados.
- `docs/TRASPASO_PE3.md` para la app: la carpeta de la corrida, las tablas de Recall@k y de híbrida contra vectorial, el resultado de las pruebas de permisos, los hallazgos y qué tiene que mostrar el PDF por criterio de la rúbrica.

## 9. Criterios de aceptación

- [ ] `python -m src.rag.ingestar` procesa `documentos/` en un solo comando y deja el manifiesto.
- [ ] Cada fragmento tiene documento, sección, versión, hash y los booleanos de rol.
- [ ] `buscar()` aplica el filtro de rol en la consulta a ChromaDB y BM25 trabaja solo con fragmentos autorizados.
- [ ] Hay una prueba por rol y la prueba de la frase testigo pasa en resultados y en el prompt.
- [ ] La medición muestra Recall@3 y Recall@5 para vectorial, BM25 e híbrida, con las dos configuraciones de fragmentado y la ganadora.
- [ ] Hay al menos 2 consultas donde la híbrida acierta y la vectorial falla.
- [ ] Las 2 preguntas sin respuesta y las 2 restringidas devuelven `requiere_humano = true` y ninguna cita inventada.
- [ ] Toda cita de `fundamento` está entre las fuentes recuperadas; la regla H-02 está activa.
- [ ] La CI sigue en verde sin clave (la ingesta de prueba usa un corpus mínimo o un embedding simulado si el modelo real no se puede bajar en la CI).
- [ ] Federico revisó SOP-CC-001 y las 10 preguntas antes de la corrida real.
- [ ] Tag `pe3` puesto y verificado con `git ls-remote --tags origin` **antes** de entregar.
