# CLAUDE.md — fde-control-cambios

Instrucciones permanentes para cualquier sesión de Claude que trabaje en este repo (Claude Code en la terminal o Claude en la app). Leer también `docs/ESTADO.md` (dónde estamos) y `docs/DECISIONES.md` (por qué es así) antes de cambiar algo.

## Qué es

Proyecto integrador del curso **Forward Deployed Engineer** (Coderhouse, 2026) de Federico Bongiovanni. Un sistema de IA que propone la **evaluación de impacto de cambios GxP (CCAM)** en un laboratorio farmacéutico ficticio, siempre como borrador para la firma de QA. Crece una capa por pre-entrega (PE2 a PE10) y cada estado se marca con un tag de git (`pe2`, `pe3`, ...).

## Quién es el usuario

Federico es especialista en QA/CSV farmacéutico (GAMP 5, 21 CFR Part 11, Anexo 11, ALCOA+). **No programa**: dirige la arquitectura y las decisiones. Por eso:

- Explicar cada cambio en lenguaje de procedimiento, no de programador, y con su equivalente GxP cuando ayude.
- Antes de un cambio grande, decir qué archivo se toca y por qué; después, cómo probarlo.
- Español rioplatense en comentarios, docs, mensajes de error y commits.

## Reglas que no se rompen

1. **El modelo propone, nunca decide.** `Salida.estado` es siempre `BORRADOR_PENDIENTE_QA`. Ninguna capa futura (agente, integración) registra algo sin aprobación humana.
2. **Ninguna clave en el código ni en el repo.** Solo en `.env` (está en `.gitignore`). No imprimir claves ni pegarlas en docs.
3. **Datos ficticios.** SOPs, CCAM y sistemas de prueba son inventados. Nunca usar datos reales de una empresa.
4. **Texto libre solo para lo que lee una persona.** Lo que decide o se registra va cerrado: Enum, rango, patrón, valor fijo.
5. **Nunca un traceback al usuario.** Todo fallo sale como `ErrorEstructurado` con tipo, campos y acción.
6. **Toda ejecución deja rastro** en `logs/ejecuciones.jsonl`, con `trace_id` y `version_prompt`, sin el texto del CCAM.
7. **El proveedor de IA es intercambiable** (`src/proveedores.py`): el resto del código no conoce a Anthropic ni a OpenAI.
8. **Los prompts viven en `prompts/`**, nunca escritos dentro de una función.
9. **Los permisos se aplican antes de buscar** (`where` por rol en ChromaDB y BM25 solo sobre lo autorizado). Nunca filtrar después.
10. **Ninguna escritura sin aprobación de QA formal** (rol `jefe_qa`) y nunca de quien la pidió: se controla en el agente y en el servidor MCP.
11. **Claude no acepta `temperature`** desde la API 2026-10-21: no agregarla al proveedor de Anthropic.

## Mapa del código

| Archivo | Qué hace |
| --- | --- |
| `src/contrato.py` | `Entrada`, `Salida`, `ErrorEstructurado`, Enums, catálogo de SOPs y reglas cruzadas |
| `src/motor.py` | `evaluar()`: valida entrada, arma prompts, llama, valida salida, reintenta 1 vez, mide, registra |
| `src/proveedores.py` | `ProveedorAnthropic`, `ProveedorOpenAI`, `ProveedorSimulado`, `crear_proveedor()` |
| `prompts/` | `sistema.md`, `usuario.md`, `correccion.md` (PE2); `sistema_rag.md`, `pregunta_rag.md` (PE3) |
| `src/rag/` | `corpus.py` (lectura y fragmentado), `embeddings.py`, `ingestar.py`, `buscar.py` (híbrida con pre-filtro por rol), `responder.py` |
| `src/agente/grafo.py` | PE4: agente LangGraph (decidir, ejecutar, pedir_aprobacion con interrupt, responder), `Decision`, límite de pasos, `SqliteSaver` |
| `src/mcp_servidor.py` · `src/cliente_mcp.py` · `src/sistema.py` | PE4: servidor MCP (3 herramientas), cliente stdio y sistema simulado SQLite con auditoría |
| `documentos/` | Corpus ficticio de la PE3 con carátula YAML y roles de lectura |
| `evals/` | Preguntas de prueba de la recuperación |
| `scripts/corrida_pe3.py` | Corrida única de la PE3 en `resultados/corrida_pe3_*/` |
| `config/` | `catalogo_sops.json` (7 SOPs ficticios), `precios.json` (USD por millón de tokens), `usuarios.json` y `rag.json` (PE3) |
| `consultas/` | 15 CCAM de medición con el campo `esperado` y la `justificacion_qa` (criterio de Federico) |
| `scripts/corrida.py` | Corrida única: casos, errores, `medicion.*` y `manifiesto.json` en `resultados/corrida_*/` |
| `.github/workflows/pruebas.yml` | CI: clon limpio, instala y corre las pruebas sin clave en cada push |
| `tests/` | Pruebas sin gastar tokens (contrato y motor con el simulador) |
| `notebooks/demo_colab.ipynb` | Demo en Colab para que terceros prueben el motor |
| `docs/COMO_FUNCIONA.md` | Explicación para no programadores; mantenerla al día con cada cambio |
| `docs/ESTADO.md` · `docs/DECISIONES.md` | Traspaso entre sesiones y registro de decisiones |
| `docs/PEDIDO_*.md` | Pedidos de trabajo escritos desde la app de Claude para Claude Code |

## Comandos

```bash
python -m pytest -q                                              # siempre antes de commitear
python -m src.motor consultas/01_version_software.json           # un CCAM con el proveedor de .env
python -m src.motor consultas/01_version_software.json --simulado invalido   # sin clave
python -m scripts.corrida                                        # medición y evidencia en una sola carpeta
python -m scripts.corrida --simulado valido                      # lo mismo, sin clave
python -m src.rag.ingestar                                       # PE3: carga documentos/ en ChromaDB
python -m scripts.corrida_pe3                                    # PE3: medición completa en una carpeta
python -m scripts.corrida_pe3 --simulado rag_valido --embeddings-simulados   # sin clave ni descarga
python -m scripts.cliente_mcp                                    # PE4: prueba el servidor MCP
python -m scripts.agente --usuario u_analista_qa --thread t1 "..."   # PE4: conversar; --aprobar/--rechazar u_jefe_qa
python -m scripts.corrida_pe4 [--simulado]                       # PE4: 5 conversaciones con traza
```

## Cómo trabajar

- Cada cambio de comportamiento lleva su prueba en `tests/` y no rompe las existentes.
- Si cambia el contrato, actualizar `README.md`, `docs/COMO_FUNCIONA.md` y las pruebas en el mismo cambio.
- Al cerrar una sesión de trabajo: actualizar `docs/ESTADO.md` (qué se hizo, qué falta, próximos pasos) y, si se tomó una decisión de diseño, agregarla a `docs/DECISIONES.md`.
- Commits chicos, en español, que digan qué cambió y para qué pre-entrega.
- No cambiar `consultas/*/esperado` sin que Federico lo confirme: es su criterio de QA.
- **Una sola corrida por entrega:** los números del PDF salen de una carpeta `resultados/corrida_*` y de nada más.
- **Tags:** se ponen y se verifican con `git ls-remote --tags origin` antes de entregar; no se mueven nunca (las correcciones van en `peN.1`).
- Las reglas de la consigna y la rúbrica de cada pre-entrega están resumidas en `docs/ESTADO.md`.
