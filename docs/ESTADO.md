# Estado del proyecto

Archivo de traspaso entre sesiones. Quien trabaje en el repo (Claude Code, Claude en la app o Federico) lo lee al empezar y lo actualiza al terminar. Lo más nuevo va arriba en la bitácora.

## Dónde estamos

**Pre-entrega en curso:** cierre de las correcciones de la PE2; después, PE3 (`docs/PEDIDO_PE3.md`).

| Pieza | Estado |
| --- | --- |
| PE2 entregada y evaluada | Hecha. Devolución con 4 correcciones: ver `docs/PEDIDO_CORRECCIONES_PE2.md` |
| Tag `pe2` sobre `c92b40d` | **Pendiente**: la app puede subir ramas pero no tags; lo sube Federico o Claude Code |
| Corrida única `scripts.corrida` con manifiesto y hashes | Hecha (D-14) |
| CI en GitHub Actions sin clave | Hecha (D-15); primera ejecución en verde sobre `e6e314f` |
| Prueba desde un clon limpio | Hecha el 2026-11-16: 23 pruebas y corrida simulada en verde |
| 10 casos nuevos clasificados por Federico | Hechos (D-18) |
| Corrida real con 15 casos | Hecha: `resultados/corrida_20261116_1116/` |
| PE3: RAG con permisos | Pedido escrito, sin empezar |

## Próximos pasos

1. Subir el tag `pe2` desde la máquina de Federico: `git tag -a pe2 c92b40d -m "Pre-Entrega 2"` y `git push origin pe2`; verificar con `git ls-remote --tags origin`.
2. Decidir con Federico si se reenvía la PE2 corregida como `pe2.1` o si las correcciones quedan como base de la PE3.
3. Federico decide la observación O-1 (campo `recomendacion`).
4. Empezar la PE3 según `docs/PEDIDO_PE3.md`. El hallazgo H-14 define el contenido de la matriz de SOP-CC-001.

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

### Corrida 2026-11-16 (`resultados/corrida_20261116_1116/`, 15 casos, Haiku 5.5)

15/15 válidas, 1 intento cada una; 3,97 s de promedio (peor caso 5,2 s); USD 0,00068 por CCAM. Coincidencia con QA: **11/15 (73 %)**; originales 4/5, anclas 2/4, frontera 5/6; críticos 3/3.

- **H-14 Sesgo sistemático hacia arriba.** Los 4 desaciertos son sobreclasificaciones de un nivel y no hay ninguna subclasificación: 01 (crítico, QA mayor), 06 (mayor, QA menor), 09 (mayor, QA menor) y 11 (crítico, QA mayor). El modelo razona «toca un sistema validado ⇒ al menos mayor» y «podría comprometer datos ⇒ crítico». El criterio de QA mide el **efecto** sobre el producto, el paciente, la decisión de liberación y la integridad de datos, no si el sistema está validado. Esa diferencia es el contenido central de la matriz de SOP-CC-001 en la PE3.
- **H-15 Lo crítico no se le escapa.** Los 3 críticos esperados (firma de liberación, audit trail, proceso fuera de rango) salen críticos. Desde el riesgo GxP es el error del lado seguro, pero genera trabajo de validación innecesario en las anclas menores.
- **H-16 El caso 14 (frontera menor/mayor) coincidió** con la clasificación conservadora de QA (mayor).
- **H-01 se confirma** por tercera vez en el CCAM 01: crítico en las tres corridas.

### Corrida de la PE2 (2026-10-30)

Detalle en `docs/TRASPASO_PE2.md` (H-01 a H-13) y archivos en `resultados/historico/pe2_entregado/`.

## Bitácora

- **2026-11-16** · Claude (app): correcciones de la devolución de la PE2. `scripts.corrida` reemplaza a `medir` y `evidencia` (una sola fuente de verdad, manifiesto y hashes); CI en GitHub Actions; 10 casos nuevos clasificados por Federico; prueba desde clon limpio en verde (23 pruebas). Corrida real de 15 casos en la máquina de Federico, sin que la clave salga de ella: 73 % de coincidencia, sesgo hacia arriba (H-14). Lo entregado en la PE2 pasó a `resultados/historico/`. Subido a `main` con la CI en verde; el tag `pe2` no se pudo subir desde la app.
- **2026-10-30** · Claude Code: corrida real con la clave de Federico (`scripts.evidencia` y `scripts.medir`): 5/5 validan, 80 % de coincidencia con QA (H-01). Techo de salida a 3.000 tokens (D-13). Escrito `docs/TRASPASO_PE2.md` para que Claude en la app arme el PDF. Tag `pe2` pendiente de la aprobación del PDF.
- **2026-10-30** · Claude Code: el repo se mudó a `C:\proyectos\ccam-llm` (la ruta vieja tenía espacios y el carácter `´`, que rompía la terminal). La carpeta vieja ya no se usa.
- **2026-10-30** · Claude Code: unificadas las dos copias del proyecto en `C:\proyectos\Agente LLm para CCAM´s\fde-control-cambios` (el código del 30/10 venía de OneDrive y los docs, de la carpeta de proyectos). Creado `.venv`, 16 pruebas en verde, `.gitignore` cubre cualquier `.env.*`, repo git local con commit inicial. Repo destino: `CFR21-VSC/ccam-llm`; README y notebook ya apuntan ahí.
- **2026-10-30** · Claude (app): agregado `docs/PEDIDO_INTERFAZ.md`, el pedido para Claude Code de la interfaz visual local.
- **2026-10-30** · Claude (app): sumados `scripts/evidencia.py`, `notebooks/demo_colab.ipynb`, este archivo, `CLAUDE.md` y `docs/DECISIONES.md`. Corregido: sin clave, el motor tiraba un traceback; ahora devuelve `api_autenticacion` (prueba nueva, 16 en verde). Repo copiado e instalado en la carpeta FDE de Federico.
- **2026-10-26** · Claude (app): motor de la PE2 completo, 15 pruebas, mapa interactivo del motor y `docs/COMO_FUNCIONA.md`. Descubierto que Claude ya no acepta `temperature`.
