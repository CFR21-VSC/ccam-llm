# Estado del proyecto

Archivo de traspaso entre sesiones. Quien trabaje en el repo (Claude Code, Claude en la app o Federico) lo lee al empezar y lo actualiza al terminar. Lo más nuevo va arriba en la bitácora.

## Dónde estamos

**Pre-entrega en curso:** PE4 (agente con LangGraph, MCP y aprobación humana). Sistema hecho y corrida real hecha; falta el PDF.

| Pieza | Estado |
| --- | --- |
| Tags `pe2` y `pe3` | Subidos por Federico y verificados con `git ls-remote` |
| Sistema simulado `src/sistema.py` (SQLite + auditoría) y semilla `datos/ccam_semilla.json` | Hecho |
| Servidor MCP `src/mcp_servidor.py`: `consultar_ccam`, `listar_ccam` (lectura), `registrar_evaluacion` (escritura) | Hecho; probado con `scripts/cliente_mcp.py` |
| Agente `src/agente/grafo.py`: decidir, ejecutar, pedir_aprobacion (interrupt), responder; límite de pasos; `SqliteSaver` | Hecho (D-29 a D-34) |
| Pruebas | 60 en verde (16 de la PE4), también en la CI con cliente MCP y corrida PE4 simulada |
| Corrida real PE4 | `resultados/corrida_pe4_20261117_0015/` (commit `6510e38`). Las dos anteriores en `historico/` |
| Bitácora del asistente | `docs/BITACORA_PE4.md` |
| PDF de la PE4 | En armado |
| Tag `pe4` | Pendiente, después del PDF |

## Próximos pasos

1. Federico aprueba el PDF de la PE4 y sube el tag `pe4`.
2. Arreglar H-28 (la búsqueda del agente corta los fragmentos a 700 caracteres) en `pe4.1` o en la PE5.
3. PE5: reemplazar `src/sistema.py` por la integración con un sistema legacy sin cambiar el contrato MCP.
4. PE6: casos nuevos con el corpus congelado y corridas repetidas (H-24).

## Contexto del caso (de la PE1)

- **Problema:** la evaluación de impacto de los CCAM es manual y sin criterio uniforme, y el seguimiento depende de un encargado que no da abasto.
- **Datos del relevamiento:** 100 a 150 CCAM nuevos por mes; 741 abiertos sobre 3.461 iniciados (21,4 %); el más antiguo lleva 3 años y 7 meses; un CCAM simple previsto en 21 días tarda 4 meses o más.
- **Historias:** HU-01, propuesta de clasificación con SOPs citados, en menos de 30 s (deseable 20 s). HU-02, aprobación de QA antes de registrar, con quién y cuándo, y visibilidad solo para los involucrados.
- **KPIs:** negocio, ciclo de un CCAM simple de 120+ días a 40 o menos. Técnico, coincidencia con QA ≥ 90 % sobre un golden dataset.
- **Riesgos:** R1 regulatorio (IA generativa en decisión GMP, borrador del Anexo 22), R2 confidencialidad, R3 clasificación sin fundamento.

## Hoja de ruta del curso

| PE | Capa | Qué se suma al repo |
| --- | --- | --- |
| 2 | Motor LLM | Lo actual |
| 3 | RAG con permisos | SOPs ficticios como documentos, búsqueda híbrida, visibilidad por rol (reemplaza el catálogo cerrado del prompt) |
| 4 | Agente | LangGraph y MCP; acción de escritura que se pausa hasta la aprobación de QA |
| 5 | Integración | Sistema de cambios simulado con API, webhooks y autenticación |
| 6 | Evals | Golden dataset, juez LLM, A/B Haiku contra Sonnet, `run_evals.py` |
| 7 | Seguridad | Prompt injection bloqueado y auditado, fuga de datos, audit trail |
| 8 | Despliegue | Docker Compose, URL pública con `/salud` y `/consulta`, `trace_id` de punta a punta |
| 9 | Traspaso | Runbook y ROI contra la línea de base de la PE1 |
| 10 | Final | Dossier, demo de 5 minutos y defensa en vivo |

## Hallazgos de las corridas

### Correcciones de la devolución de la PE3 (`resultados/corrida_correcciones_pe3_20261123_1241/`, Haiku 5.5)

Devolución recibida el 2026-11-23. M-1 (método de A y B), M-2 (definición formal del acierto), M-3 (objeto completo de `responder()` con `fuentes` separada de `fundamento`), M-5 (tablas) y M-6 (regresión de seguridad: 53 consultas directas y parafraseadas desde roles sin permiso, 0 fugas, también en la CI) hechas. M-4: corpus congelado (`evals/corpus_congelado.json`, `845258f9…`) **antes** de escribir los casos 201-210; Federico los clasificó sin ver al sistema.

- **H-29 Generalización: 5/10 con casos nuevos** contra 11/15 con los casos conocidos. Errores: 201 mayor (QA menor, sobre), 203 menor (QA fuera de alcance), 204 mayor (QA crítico, **sub**), 206 requiere humano (QA mayor), 209 menor (QA mayor, **sub**). Revalidación: 8/10.
- **H-30 Subclasificación con la regla delante:** en 209 el modelo citó SOP-CC-001 §5.7 y leyó solo «texto aprobado», omitiendo «o arte». Federico tampoco la recordó al clasificar: la regla es fácil de pasar por alto y conviene un ejemplo en §5.7 (en una versión nueva, con corpus re-congelado).
- **H-31 Huecos de corpus:** 203 (el SOP no dice que el reemplazo idéntico en mantenimiento preventivo queda fuera de control de cambios) y 206 (no hay SOP de validación de proceso: el sistema derivó a QA en vez de inventar). 204: no hay regla que diga que automatizar un cálculo que respalda liberación es crítico.

### Corrida PE4 2026-11-17 (`resultados/corrida_pe4_20261117_0015/`, Haiku 5.5)

Las 5 conversaciones salieron como se esperaba: C1 (documentos) y C2 (sistema) solo consultan; C3 evalúa el CCAM-2026-101, pide registrar, se pausa, **se retoma en otro proceso** con el thread_id C3 y lo aprueba u_jefe_qa; C4 evalúa el CCAM-2026-108 (crítico), pide registrar y u_jefe_qa rechaza: no se escribe nada; C5 corta en el paso 3 de 3 con mensaje. Una sola escritura en el sistema, con su fila de auditoría. USD 0,0113 en total.

- **H-25** (primera corrida, en `historico/pe4_primera_corrida/`): el modelo leyó «requiere aprobación humana previa» como que la aprobación tenía que existir antes y no pidió la escritura. Se aclaró que elegir la acción es pedir la aprobación.
- **H-26** (primera corrida): la respuesta final superó el máximo y cerró con error estructurado. Tope en prompt y contrato.
- **H-27** (segunda corrida, en `historico/pe4_segunda_corrida/`): con «Paso 3 de 3» a la vista, el modelo cerró solo y la barrera de código quedó sin probar. D-33.
- **H-28** (corrida final, C1): `buscar_documentos` le pasa al modelo los fragmentos cortados a 700 caracteres; el §3.2 de SOP-VS-003 quedó a medias y el modelo **lo dijo en vez de inventar**. Arreglo pendiente.
- **H-02 en el agente:** en C4 el motor propuso una tarea que nombraba SOP-VS-002 sin citarlo; la regla cruzada lo rechazó y el reintento lo corrigió.

### Corrida PE3 final 2026-11-16 (`resultados/corrida_pe3_20261116_1224/`, SOP-CC-001 v4, Haiku 5.5, config A)

Fuente única del PDF de la PE3 (commit `d71d887`, prompt `rag-9b8f1eede363`). Recuperación: híbrida 100 % a k = 3 y 5 en A y B; vectorial 71 % / 86 % en A. Híbrida acierta y vectorial falla en 4 (P04, CAPA-2026-014, CAPA-2026-041, R-QA-01). Permisos: 12/12. Preguntas: 10/10. CCAM: 15/15 válidos en el primer intento, **11/15 (73 %)**, 1 sobre y 1 subclasificación; 6.166 tokens de entrada, USD 0,0010 por CCAM, 3,9 s (peor 6,3 s).

- **H-20 y H-21 resueltos con SOP-CC-001 v4 (D-28):** el caso 02 (estuche con QR) pasa a mayor y el 15 (antivirus) a sin impacto, como QA.
- **H-23 El umbral se come un fuera de alcance.** El caso 05 (aguinaldo) bajó de 0,22 a 0,10 de similitud porque cambió el texto de SOP-CC-001 §2, quedó debajo de 0,20 y salió `requiere_humano` sin llamar al modelo, en lugar de `fuera_de_alcance`. Los dos derivan a QA sin clasificar (lado seguro), pero la barrera previa no distingue «no es un cambio» de «no hay evidencia». Para la PE4: que el pre-filtro por umbral solo se aplique si la consulta parece un cambio, o dejar que el modelo decida siempre.
- **H-24 Efecto colateral de la v4 en el caso 09 (perfil de solo consulta): sin impacto, QA menor.** El modelo leyó la nueva §5.2 como «no altera nada» aunque el LIMS es un sistema GxP. Subclasificación de un nivel. La §5.2 dice «ningún sistema GxP»: es un error de lectura del modelo, no del SOP, pero aparece justo con el cambio de texto. Arreglar 2 casos movió otros 2: la PE6 tiene que medir con corridas repetidas y casos nuevos, no ajustar el SOP caso por caso.
- **H-19 sigue:** el 11 (cámara de estabilidad) vuelve a salir crítico citando §5.6. Va al A/B de modelos de la PE6.
- **H-22 sigue:** el 04 (impresora) sale `requiere_humano`, lado seguro.

### Corrida PE3 con SOP-CC-001 v3 (`resultados/historico/pe3_corrida_sop_cc_001_v3/`)

11/15 con 1 sobre y 1 subclasificación. Originó H-17 a H-22 (la primera corrida, cortada por H-18, está en `historico/pe3_corrida_interrumpida/`). H-20: el 02 salió menor porque §5.7 no incluía el rotulado aprobado. H-21: el 15 salió fuera de alcance porque §2 y §5.2 decían casi lo mismo. H-17: el modelo de embeddings lee 128 tokens (D-22). H-18: justificación de más de 1.200 caracteres (tope de 900 en el prompt).

### Corrida 2026-11-16 (`resultados/corrida_20261116_1116/`, 15 casos, Haiku 5.5)

15/15 válidas, 1 intento cada una; 3,97 s de promedio (peor caso 5,2 s); USD 0,00068 por CCAM. Coincidencia con QA: **11/15 (73 %)**; originales 4/5, anclas 2/4, frontera 5/6; críticos 3/3.

- **H-14 Sesgo sistemático hacia arriba.** Los 4 desaciertos son sobreclasificaciones de un nivel y no hay ninguna subclasificación: 01 (crítico, QA mayor), 06 (mayor, QA menor), 09 (mayor, QA menor) y 11 (crítico, QA mayor). El modelo razona «toca un sistema validado ⇒ al menos mayor» y «podría comprometer datos ⇒ crítico». El criterio de QA mide el **efecto** sobre el producto, el paciente, la decisión de liberación y la integridad de datos, no si el sistema está validado. Esa diferencia es el contenido central de la matriz de SOP-CC-001 en la PE3.
- **H-15 Lo crítico no se le escapa.** Los 3 críticos esperados (firma de liberación, audit trail, proceso fuera de rango) salen críticos. Desde el riesgo GxP es el error del lado seguro, pero genera trabajo de validación innecesario en las anclas menores.
- **H-16 El caso 14 (frontera menor/mayor) coincidió** con la clasificación conservadora de QA (mayor).
- **H-01 se confirma** por tercera vez en el CCAM 01: crítico en las tres corridas.

### Corrida de la PE2 (2026-10-30)

Detalle en `docs/TRASPASO_PE2.md` (H-01 a H-13) y archivos en `resultados/historico/pe2_entregado/`.

## Bitácora

- **2026-11-23** · Claude (app): correcciones de la devolución de la PE3 (M-1 a M-6). Corpus congelado, 10 casos nuevos clasificados por Federico (209 mayor por §5.7 v4; 208 requiere humano), corrida real `corrida_correcciones_pe3_20261123_1241`: seguridad 0 fugas en 53 consultas, top-k 6/6 en el puesto 1, casos nuevos 5/10 (H-29 a H-31).
- **2026-11-17** · Claude (app): PE4 completa en código. Sistema simulado, servidor MCP propio, agente LangGraph con interrupt y SqliteSaver, aprobación de QA formal distinta de quien pide (decisión de Federico), 16 pruebas, CI. Tres corridas reales en la máquina de Federico: las dos primeras dejaron H-25 a H-27 y quedan en `historico/`; la final es `corrida_pe4_20261117_0015`.
- **2026-11-16** · Claude (app): Federico aprobó las 10 preguntas y decidió H-20 y H-21; SOP-CC-001 v4 (D-28) y corrida final `corrida_pe3_20261116_1224` (11/15; resuelve 02 y 15, aparecen H-23 y H-24). PDF de la PE3 rearmado desde esa carpeta.
- **2026-11-16** · Claude (app): PE3 completa en código. Corpus ficticio, `src/rag/` (ingesta ChromaDB, híbrida vectorial + BM25 con RRF y pre-filtro por rol, `responder` y `responder_pregunta`), `Salida.requiere_humano`, citas validadas contra lo recuperado, regla H-02, 44 pruebas y CI. Corrida real en la máquina de Federico (la clave no salió de ella; las librerías se pasaron por el puente porque la máquina no llega a files.pythonhosted.org). La primera corrida se cortó (H-18) y se guardó en `historico/`.
- **2026-11-16** · Claude (app): correcciones de la devolución de la PE2. `scripts.corrida` reemplaza a `medir` y `evidencia` (una sola fuente de verdad, manifiesto y hashes); CI en GitHub Actions; 10 casos nuevos clasificados por Federico; prueba desde clon limpio en verde (23 pruebas). Corrida real de 15 casos en la máquina de Federico, sin que la clave salga de ella: 73 % de coincidencia, sesgo hacia arriba (H-14). Lo entregado en la PE2 pasó a `resultados/historico/`. Subido a `main` con la CI en verde; el tag `pe2` no se pudo subir desde la app.
- **2026-10-30** · Claude Code: corrida real con la clave de Federico (`scripts.evidencia` y `scripts.medir`): 5/5 validan, 80 % de coincidencia con QA (H-01). Techo de salida a 3.000 tokens (D-13). Escrito `docs/TRASPASO_PE2.md` para que Claude en la app arme el PDF. Tag `pe2` pendiente de la aprobación del PDF.
- **2026-10-30** · Claude Code: el repo se mudó a `C:\proyectos\ccam-llm` (la ruta vieja tenía espacios y el carácter `´`, que rompía la terminal). La carpeta vieja ya no se usa.
- **2026-10-30** · Claude Code: unificadas las dos copias del proyecto en `C:\proyectos\Agente LLm para CCAM´s\fde-control-cambios` (el código del 30/10 venía de OneDrive y los docs, de la carpeta de proyectos). Creado `.venv`, 16 pruebas en verde, `.gitignore` cubre cualquier `.env.*`, repo git local con commit inicial. Repo destino: `CFR21-VSC/ccam-llm`; README y notebook ya apuntan ahí.
- **2026-10-30** · Claude (app): agregado `docs/PEDIDO_INTERFAZ.md`, el pedido para Claude Code de la interfaz visual local.
- **2026-10-30** · Claude (app): sumados `scripts/evidencia.py`, `notebooks/demo_colab.ipynb`, este archivo, `CLAUDE.md` y `docs/DECISIONES.md`. Corregido: sin clave, el motor tiraba un traceback; ahora devuelve `api_autenticacion` (prueba nueva, 16 en verde). Repo copiado e instalado en la carpeta FDE de Federico.
- **2026-10-26** · Claude (app): motor de la PE2 completo, 15 pruebas, mapa interactivo del motor y `docs/COMO_FUNCIONA.md`. Descubierto que Claude ya no acepta `temperature`.
