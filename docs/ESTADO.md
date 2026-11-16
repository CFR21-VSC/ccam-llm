# Estado del proyecto

Archivo de traspaso entre sesiones. Quien trabaje en el repo (Claude Code, Claude en la app o Federico) lo lee al empezar y lo actualiza al terminar. Lo más nuevo va arriba en la bitácora.

## Dónde estamos

**Pre-entrega en curso:** PE3 (RAG con permisos). Sistema hecho y corrida real hecha; falta la revisión de Federico y el PDF.

| Pieza | Estado |
| --- | --- |
| Tag `pe2` sobre `c92b40d` | **Pendiente**: la app no puede subir tags; lo sube Federico |
| Correcciones de la PE2 (corrida única, CI, 10 casos, clon limpio) | Hechas |
| Corpus `documentos/` (7 SOPs + 3 restringidos con frase testigo) | Hecho (D-19, D-20). SOP-CC-001 v4 por decisión de Federico (D-28) |
| `src/rag/`: ingesta, búsqueda híbrida con pre-filtro, `responder()` | Hecho (D-21 a D-26) |
| Pruebas PE3 (permisos por rol, testigo en resultados y prompt, RRF, citas, H-02) | Hechas: 44 en verde, también en la CI |
| `evals/preguntas_pe3.json` (10) y `evals/consultas_codigos.json` (8) | Hechas y **aprobadas por Federico** el 2026-11-16 |
| Corrida real PE3 | Hecha con SOP-CC-001 v4: `resultados/corrida_pe3_20261116_1224/` (commit `d71d887`). La de la v3 quedó en `historico/` |
| PDF de la PE3 | En armado desde esa carpeta |
| Tag `pe3` | Pendiente, después del PDF |

## Próximos pasos

1. Federico aprueba el PDF armado desde `corrida_pe3_20261116_1224`.
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

- **2026-11-16** · Claude (app): Federico aprobó las 10 preguntas y decidió H-20 y H-21; SOP-CC-001 v4 (D-28) y corrida final `corrida_pe3_20261116_1224` (11/15; resuelve 02 y 15, aparecen H-23 y H-24). PDF de la PE3 rearmado desde esa carpeta.
- **2026-11-16** · Claude (app): PE3 completa en código. Corpus ficticio, `src/rag/` (ingesta ChromaDB, híbrida vectorial + BM25 con RRF y pre-filtro por rol, `responder` y `responder_pregunta`), `Salida.requiere_humano`, citas validadas contra lo recuperado, regla H-02, 44 pruebas y CI. Corrida real en la máquina de Federico (la clave no salió de ella; las librerías se pasaron por el puente porque la máquina no llega a files.pythonhosted.org). La primera corrida se cortó (H-18) y se guardó en `historico/`.
- **2026-11-16** · Claude (app): correcciones de la devolución de la PE2. `scripts.corrida` reemplaza a `medir` y `evidencia` (una sola fuente de verdad, manifiesto y hashes); CI en GitHub Actions; 10 casos nuevos clasificados por Federico; prueba desde clon limpio en verde (23 pruebas). Corrida real de 15 casos en la máquina de Federico, sin que la clave salga de ella: 73 % de coincidencia, sesgo hacia arriba (H-14). Lo entregado en la PE2 pasó a `resultados/historico/`. Subido a `main` con la CI en verde; el tag `pe2` no se pudo subir desde la app.
- **2026-10-30** · Claude Code: corrida real con la clave de Federico (`scripts.evidencia` y `scripts.medir`): 5/5 validan, 80 % de coincidencia con QA (H-01). Techo de salida a 3.000 tokens (D-13). Escrito `docs/TRASPASO_PE2.md` para que Claude en la app arme el PDF. Tag `pe2` pendiente de la aprobación del PDF.
- **2026-10-30** · Claude Code: el repo se mudó a `C:\proyectos\ccam-llm` (la ruta vieja tenía espacios y el carácter `´`, que rompía la terminal). La carpeta vieja ya no se usa.
- **2026-10-30** · Claude Code: unificadas las dos copias del proyecto en `C:\proyectos\Agente LLm para CCAM´s\fde-control-cambios` (el código del 30/10 venía de OneDrive y los docs, de la carpeta de proyectos). Creado `.venv`, 16 pruebas en verde, `.gitignore` cubre cualquier `.env.*`, repo git local con commit inicial. Repo destino: `CFR21-VSC/ccam-llm`; README y notebook ya apuntan ahí.
- **2026-10-30** · Claude (app): agregado `docs/PEDIDO_INTERFAZ.md`, el pedido para Claude Code de la interfaz visual local.
- **2026-10-30** · Claude (app): sumados `scripts/evidencia.py`, `notebooks/demo_colab.ipynb`, este archivo, `CLAUDE.md` y `docs/DECISIONES.md`. Corregido: sin clave, el motor tiraba un traceback; ahora devuelve `api_autenticacion` (prueba nueva, 16 en verde). Repo copiado e instalado en la carpeta FDE de Federico.
- **2026-10-26** · Claude (app): motor de la PE2 completo, 15 pruebas, mapa interactivo del motor y `docs/COMO_FUNCIONA.md`. Descubierto que Claude ya no acepta `temperature`.
