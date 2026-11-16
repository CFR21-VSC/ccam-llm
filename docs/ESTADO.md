# Estado del proyecto

Archivo de traspaso entre sesiones. Quien trabaje en el repo (Claude Code, Claude en la app o Federico) lo lee al empezar y lo actualiza al terminar. Lo más nuevo va arriba en la bitácora.

## Dónde estamos

**Pre-entrega en curso:** PE3 (RAG con permisos). Sistema hecho y corrida real hecha; falta la revisión de Federico y el PDF.

| Pieza | Estado |
| --- | --- |
| Tag `pe2` sobre `c92b40d` | **Pendiente**: la app no puede subir tags; lo sube Federico |
| Correcciones de la PE2 (corrida única, CI, 10 casos, clon limpio) | Hechas |
| Corpus `documentos/` (7 SOPs + 3 restringidos con frase testigo) | Hecho (D-19, D-20). **Federico tiene que revisar SOP-CC-001 §5** |
| `src/rag/`: ingesta, búsqueda híbrida con pre-filtro, `responder()` | Hecho (D-21 a D-26) |
| Pruebas PE3 (permisos por rol, testigo en resultados y prompt, RRF, citas, H-02) | Hechas: 44 en verde, también en la CI |
| `evals/preguntas_pe3.json` (10) y `evals/consultas_codigos.json` (8) | Hechas. **Federico tiene que revisarlas** |
| Corrida real PE3 | Hecha: `resultados/corrida_pe3_20261116_1152/` (commit `bee7fdc`, prompt `rag-9b8f1eede363`) |
| PDF de la PE3 | En armado desde esa carpeta |
| Tag `pe3` | Pendiente, después del PDF |

## Próximos pasos

1. Federico revisa SOP-CC-001 §5 (en especial H-20 y H-21) y las 10 preguntas. Si cambia algo, se vuelve a correr `scripts.corrida_pe3` (cuesta USD 0,02) y el PDF sale de la carpeta nueva.
2. Subir los tags `pe2` y `pe3` desde la máquina de Federico; verificar con `git ls-remote --tags origin`.
3. Federico decide O-1 (campo `recomendacion`).
4. PE6: casos nuevos escritos con el corpus congelado (limitación de D-20).

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

### Corrida PE3 2026-11-16 (`resultados/corrida_pe3_20261116_1152/`, Haiku 5.5, config A)

Recuperación (14 consultas con respuesta): híbrida 100 % a k = 3 y 5 en A y B; vectorial 71 % / 86 % en A y 86 % / 93 % en B; BM25 100 %. En 4 consultas la híbrida acierta y la vectorial falla (P04, CAPA-2026-014, CAPA-2026-041, R-QA-01). Permisos: 12/12 combinaciones de frase testigo correctas; usuario desconocido, 0 fragmentos. Preguntas: 10/10 (las 2 sin respuesta y las 2 restringidas, `requiere_humano` sin citas). CCAM: 15/15 válidos en el primer intento, **11/15 (73 %)**, igual que la PE2 pero con otros errores: 1 sobre y 1 subclasificación (PE2: 4 y 0). 6.610 tokens de entrada (PE2: 2.463), USD 0,0011 por CCAM, 3,9 s.

- **H-17 El modelo de embeddings lee solo 128 tokens.** Cortaba el resto de cada fragmento sin avisar. Se resolvió con ventanas promediadas (D-22).
- **H-18 Con evidencia, el modelo escribe más.** En la primera corrida real (interrumpida, `resultados/historico/pe3_corrida_interrumpida/`) el CCAM 01 superó dos veces el tope de 1.200 caracteres de la justificación y salió como `salida_invalida`. Se agregó al prompt un tope de 900 (commit `bee7fdc`). El contrato hizo su trabajo: error estructurado, sin traceback.
- **H-19 Caso 11 (cámara de estabilidad): crítico, QA mayor.** El modelo citó SOP-CC-001 §5.6, que dice textualmente que los datos que respaldan la vida útil y no la liberación son mayor, y aun así eligió crítico. Es un error de razonamiento, no de recuperación: tenía el fragmento correcto.
- **H-20 Caso 02 (estuche con QR): menor, QA mayor. Primera subclasificación del proyecto.** Aplicó la pregunta de §5.7 ("¿modifica una función, cálculo, dato o estado validado?") y concluyó que no. El rotulado aprobado no es un "estado validado" en la redacción de la matriz: **hueco en SOP-CC-001 §5.7 que tiene que decidir Federico** (por ejemplo, sumar "o un texto o arte aprobado por la autoridad sanitaria").
- **H-21 Caso 15 (antivirus): fuera_de_alcance, QA sin_impacto.** SOP-CC-001 §2 (exclusión de alcance) y §5.2 (sin impacto) dicen casi lo mismo. El contrato distingue dos estados que el SOP no distingue. A decidir por Federico.
- **H-22 Caso 04 (impresora): requiere_humano, QA menor.** Es el comportamiento diseñado: ningún documento trata impresoras y la descripción no dice qué imprime. Desacierto en la tabla, pero del lado seguro.
- **H-14 se corrige:** los casos 01, 06 y 09 (sobreclasificados en la PE2) ahora coinciden; la matriz con "el nivel lo define el efecto" funcionó en esos tres.

### Corrida 2026-11-16 (`resultados/corrida_20261116_1116/`, 15 casos, Haiku 5.5)

15/15 válidas, 1 intento cada una; 3,97 s de promedio (peor caso 5,2 s); USD 0,00068 por CCAM. Coincidencia con QA: **11/15 (73 %)**; originales 4/5, anclas 2/4, frontera 5/6; críticos 3/3.

- **H-14 Sesgo sistemático hacia arriba.** Los 4 desaciertos son sobreclasificaciones de un nivel y no hay ninguna subclasificación: 01 (crítico, QA mayor), 06 (mayor, QA menor), 09 (mayor, QA menor) y 11 (crítico, QA mayor). El modelo razona «toca un sistema validado ⇒ al menos mayor» y «podría comprometer datos ⇒ crítico». El criterio de QA mide el **efecto** sobre el producto, el paciente, la decisión de liberación y la integridad de datos, no si el sistema está validado. Esa diferencia es el contenido central de la matriz de SOP-CC-001 en la PE3.
- **H-15 Lo crítico no se le escapa.** Los 3 críticos esperados (firma de liberación, audit trail, proceso fuera de rango) salen críticos. Desde el riesgo GxP es el error del lado seguro, pero genera trabajo de validación innecesario en las anclas menores.
- **H-16 El caso 14 (frontera menor/mayor) coincidió** con la clasificación conservadora de QA (mayor).
- **H-01 se confirma** por tercera vez en el CCAM 01: crítico en las tres corridas.

### Corrida de la PE2 (2026-10-30)

Detalle en `docs/TRASPASO_PE2.md` (H-01 a H-13) y archivos en `resultados/historico/pe2_entregado/`.

## Bitácora

- **2026-11-16** · Claude (app): PE3 completa en código. Corpus ficticio, `src/rag/` (ingesta ChromaDB, híbrida vectorial + BM25 con RRF y pre-filtro por rol, `responder` y `responder_pregunta`), `Salida.requiere_humano`, citas validadas contra lo recuperado, regla H-02, 44 pruebas y CI. Corrida real en la máquina de Federico (la clave no salió de ella; las librerías se pasaron por el puente porque la máquina no llega a files.pythonhosted.org). La primera corrida se cortó (H-18) y se guardó en `historico/`.
- **2026-11-16** · Claude (app): correcciones de la devolución de la PE2. `scripts.corrida` reemplaza a `medir` y `evidencia` (una sola fuente de verdad, manifiesto y hashes); CI en GitHub Actions; 10 casos nuevos clasificados por Federico; prueba desde clon limpio en verde (23 pruebas). Corrida real de 15 casos en la máquina de Federico, sin que la clave salga de ella: 73 % de coincidencia, sesgo hacia arriba (H-14). Lo entregado en la PE2 pasó a `resultados/historico/`. Subido a `main` con la CI en verde; el tag `pe2` no se pudo subir desde la app.
- **2026-10-30** · Claude Code: corrida real con la clave de Federico (`scripts.evidencia` y `scripts.medir`): 5/5 validan, 80 % de coincidencia con QA (H-01). Techo de salida a 3.000 tokens (D-13). Escrito `docs/TRASPASO_PE2.md` para que Claude en la app arme el PDF. Tag `pe2` pendiente de la aprobación del PDF.
- **2026-10-30** · Claude Code: el repo se mudó a `C:\proyectos\ccam-llm` (la ruta vieja tenía espacios y el carácter `´`, que rompía la terminal). La carpeta vieja ya no se usa.
- **2026-10-30** · Claude Code: unificadas las dos copias del proyecto en `C:\proyectos\Agente LLm para CCAM´s\fde-control-cambios` (el código del 30/10 venía de OneDrive y los docs, de la carpeta de proyectos). Creado `.venv`, 16 pruebas en verde, `.gitignore` cubre cualquier `.env.*`, repo git local con commit inicial. Repo destino: `CFR21-VSC/ccam-llm`; README y notebook ya apuntan ahí.
- **2026-10-30** · Claude (app): agregado `docs/PEDIDO_INTERFAZ.md`, el pedido para Claude Code de la interfaz visual local.
- **2026-10-30** · Claude (app): sumados `scripts/evidencia.py`, `notebooks/demo_colab.ipynb`, este archivo, `CLAUDE.md` y `docs/DECISIONES.md`. Corregido: sin clave, el motor tiraba un traceback; ahora devuelve `api_autenticacion` (prueba nueva, 16 en verde). Repo copiado e instalado en la carpeta FDE de Federico.
- **2026-10-26** · Claude (app): motor de la PE2 completo, 15 pruebas, mapa interactivo del motor y `docs/COMO_FUNCIONA.md`. Descubierto que Claude ya no acepta `temperature`.
