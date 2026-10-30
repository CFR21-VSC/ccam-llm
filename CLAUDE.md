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
9. **Claude no acepta `temperature`** desde la API 2026-10-21: no agregarla al proveedor de Anthropic.

## Mapa del código

| Archivo | Qué hace |
| --- | --- |
| `src/contrato.py` | `Entrada`, `Salida`, `ErrorEstructurado`, Enums, catálogo de SOPs y reglas cruzadas |
| `src/motor.py` | `evaluar()`: valida entrada, arma prompts, llama, valida salida, reintenta 1 vez, mide, registra |
| `src/proveedores.py` | `ProveedorAnthropic`, `ProveedorOpenAI`, `ProveedorSimulado`, `crear_proveedor()` |
| `prompts/` | `sistema.md`, `usuario.md`, `correccion.md` (plantillas con `$variables`) |
| `config/` | `catalogo_sops.json` (7 SOPs ficticios), `precios.json` (USD por millón de tokens) |
| `consultas/` | 5 CCAM de medición con el campo `esperado` (criterio de QA de Federico) |
| `scripts/medir.py` | Corre las 5 consultas y escribe `resultados/medicion_*.md` y `.json` |
| `scripts/evidencia.py` | Guarda en `resultados/evidencia_*.txt` la salida de terminal para el PDF |
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
python -m scripts.medir                                          # tabla de las 5 consultas
python -m scripts.evidencia                                      # evidencia de terminal para el PDF
```

## Cómo trabajar

- Cada cambio de comportamiento lleva su prueba en `tests/` y no rompe las existentes.
- Si cambia el contrato, actualizar `README.md`, `docs/COMO_FUNCIONA.md` y las pruebas en el mismo cambio.
- Al cerrar una sesión de trabajo: actualizar `docs/ESTADO.md` (qué se hizo, qué falta, próximos pasos) y, si se tomó una decisión de diseño, agregarla a `docs/DECISIONES.md`.
- Commits chicos, en español, que digan qué cambió y para qué pre-entrega.
- No cambiar `consultas/*/esperado` sin que Federico lo confirme: es su criterio de QA.
- Las reglas de la consigna y la rúbrica de cada pre-entrega están resumidas en `docs/ESTADO.md`.
