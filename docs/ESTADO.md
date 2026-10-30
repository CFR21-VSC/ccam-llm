# Estado del proyecto

Archivo de traspaso entre sesiones. Quien trabaje en el repo (Claude Code, Claude en la app o Federico) lo lee al empezar y lo actualiza al terminar. Lo más nuevo va arriba en la bitácora.

## Dónde estamos

**Pre-entrega en curso:** PE2, motor LLM base y validación estructurada.

| Pieza | Estado |
| --- | --- |
| Contrato `Entrada` / `Salida` con reglas y regla cruzada | Hecho |
| Llamada real a Claude con prompt en plantilla | Hecho, falta correrla con clave real |
| Reintento con corrección y error estructurado | Hecho |
| Captura de errores de API (401, 429, sin conexión, sin clave) | Hecho; 401 probado contra la API real |
| Medición de tokens, costo y latencia | Hecho, falta la corrida real |
| 16 pruebas sin gastar tokens | En verde |
| Demo en Colab | Hecha, falta el link del repo |
| Repo en GitHub con tag `pe2` | **Pendiente**: crear el repo y subir |
| `.env` con la clave | **Pendiente**: lo carga Federico |
| Corrida real: `scripts.medir` y `scripts.evidencia` | **Pendiente** |
| PDF `FDE_PE2_Bongiovanni_Federico.pdf` | Borrador hecho; se regenera con los resultados reales |
| Interfaz visual local (Streamlit) | **Pendiente**, después del tag `pe2`: ver `docs/PEDIDO_INTERFAZ.md` |

## Próximos pasos

1. Repo en GitHub: `https://github.com/CFR21-VSC/ccam-llm` (público). Federico carga `.env`.
2. Subir el código, `python -m pytest -q` en verde, commit inicial.
3. Correr `python -m scripts.evidencia` y `python -m scripts.medir` con la clave real.
4. Revisar las 5 respuestas contra el `esperado` de QA; si alguna clasificación es dudosa, anotarla abajo como hallazgo (sirve para el riesgo R3 y la PE6).
5. Regenerar el PDF con `resultados/` (lo hace Claude en la app), `git tag pe2`, push del tag.
6. ~~Reemplazar `<usuario>` en README y notebook~~ hecho: apuntan a `CFR21-VSC/ccam-llm`.
7. **Después del tag `pe2`:** construir la interfaz visual local según `docs/PEDIDO_INTERFAZ.md`.

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

_(vacío: completar con lo que se observe en la corrida real)_

## Bitácora

- **2026-10-30** · Claude Code: el repo se mudó a `C:proyectosam-llm` (la ruta vieja tenía espacios y el carácter `´`, que rompía la terminal). La carpeta vieja ya no se usa.
- **2026-10-30** · Claude Code: unificadas las dos copias del proyecto en `C:\proyectos\Agente LLm para CCAM´s\fde-control-cambios` (el código del 30/10 venía de OneDrive y los docs, de la carpeta de proyectos). Creado `.venv`, 16 pruebas en verde, `.gitignore` cubre cualquier `.env.*`, repo git local con commit inicial. Repo destino: `CFR21-VSC/ccam-llm`; README y notebook ya apuntan ahí.
- **2026-10-30** · Claude (app): agregado `docs/PEDIDO_INTERFAZ.md`, el pedido para Claude Code de la interfaz visual local.
- **2026-10-30** · Claude (app): sumados `scripts/evidencia.py`, `notebooks/demo_colab.ipynb`, este archivo, `CLAUDE.md` y `docs/DECISIONES.md`. Corregido: sin clave, el motor tiraba un traceback; ahora devuelve `api_autenticacion` (prueba nueva, 16 en verde). Repo copiado e instalado en la carpeta FDE de Federico.
- **2026-10-26** · Claude (app): motor de la PE2 completo, 15 pruebas, mapa interactivo del motor y `docs/COMO_FUNCIONA.md`. Descubierto que Claude ya no acepta `temperature`.
