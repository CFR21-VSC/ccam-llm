# ccam-llm

[![pruebas](https://github.com/CFR21-VSC/ccam-llm/actions/workflows/pruebas.yml/badge.svg)](https://github.com/CFR21-VSC/ccam-llm/actions/workflows/pruebas.yml)

Motor de evaluación de impacto de cambios GxP (CCAM) con un modelo de lenguaje, contrato de datos en Pydantic, medición de tokens, costo y latencia, y manejo de errores con reintento.

Proyecto integrador del curso **Forward Deployed Engineer** (Coderhouse, 2026). La etiqueta `pe2` marca lo entregado en la Pre-Entrega 2; esta versión suma las correcciones de su devolución (una sola corrida como fuente de verdad, integración continua y 10 casos nuevos clasificados por QA).

> **Datos ficticios.** El catálogo de SOPs, los CCAM de prueba y el sistema de cambios son ficticios. No hay información real de ninguna empresa.

## Qué hace

Recibe un pedido de cambio (CCAM) y devuelve una **propuesta** de evaluación de impacto GxP: nivel de impacto, si requiere revalidación, los SOPs que la fundamentan y las tareas a realizar. La propuesta es siempre un borrador (`BORRADOR_PENDIENTE_QA`): la decisión y la firma son de QA.

```
CCAM ──► valida Entrada ──► arma prompts ──► Claude ──► valida Salida ──► propuesta + métricas
              │                                              │
              └─ inválida: error, sin llamar al modelo       └─ inválida: registra el campo, reintenta 1 vez,
                                                                 y si falla de nuevo devuelve un error estructurado
```

Cómo funciona por dentro, explicado paso a paso: [docs/COMO_FUNCIONA.md](docs/COMO_FUNCIONA.md).

## Estructura

```
src/contrato.py      Clases Entrada y Salida, reglas de validación y regla cruzada
src/motor.py         Recorrido completo: validar, llamar, validar, reintentar, medir, registrar
src/proveedores.py   Conexión con Claude (Anthropic), OpenAI (opcional) y un simulador sin clave
prompts/             Plantillas del prompt: sistema, caso y corrección del reintento
config/              Catálogo ficticio de SOPs y precios por modelo
consultas/           15 CCAM de medición, cada uno con la respuesta esperada y la justificación de QA
scripts/corrida.py   Corrida única: todos los casos y errores, tabla y manifiesto en una sola carpeta
resultados/          Una carpeta por corrida; historico/ guarda lo entregado en la PE2
tests/               Pruebas del contrato, del motor y de la corrida que no gastan tokens
notebooks/           Demo en Google Colab para probar el motor con tus propios CCAM
.github/workflows/   Integración continua: instala desde cero y corre las pruebas en cada push
```

## Cómo correrlo desde un clon limpio

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/CFR21-VSC/ccam-llm.git
cd ccam-llm
python -m venv .venv
# Windows: .venv\Scripts\activate    |    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Completar `.env`:

```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-5-5
ANTHROPIC_API_KEY=<tu clave>
LLM_MAX_TOKENS=3000
```

### 1. Pruebas sin gastar tokens

```bash
python -m pytest -q
```

### 2. Evaluar un CCAM

```bash
python -m src.motor consultas/01_version_software.json
```

### 3. Corrida de medición y evidencia

```bash
python -m scripts.corrida
```

Corre los 15 CCAM y los tres casos de error **una sola vez cada uno** y guarda todo en `resultados/corrida_AAAAMMDD_HHMM/`:

| Archivo | Qué tiene |
| --- | --- |
| `caso_NN.txt` | La salida de terminal completa de ese CCAM, sin recortar |
| `caso_NN.json` | El resultado completo de esa misma ejecución |
| `error_reintento.txt` · `error_api.txt` · `error_entrada.txt` | Salida inválida con reintento, error real de la API (401) y entrada inválida |
| `medicion.md` · `medicion.json` | La tabla, armada leyendo los `caso_NN.json` de la carpeta (nunca con otra llamada) |
| `manifiesto.json` | Fecha, modelo, versión del prompt, commit y hash SHA-256 de cada archivo |

Un CCAM cuyo `esperado` diga `A_CONFIRMAR_POR_QA` se saltea hasta que QA lo clasifique. Sin clave: `python -m scripts.corrida --simulado valido`.

## Reproducir desde un clon limpio

La integración continua (badge de arriba) lo prueba en cada push: GitHub arma una máquina nueva con Python 3.11 y 3.12, clona el repo, instala `requirements.txt` y corre las pruebas y una corrida simulada, sin ninguna clave. A mano es lo mismo:

```bash
git clone https://github.com/CFR21-VSC/ccam-llm.git ccam-llm-prueba
cd ccam-llm-prueba
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
python -m scripts.corrida --simulado valido
```

Para la corrida real alcanza con copiar `.env.example` como `.env` y completar la clave.

### Probarlo en Google Colab

[`notebooks/demo_colab.ipynb`](notebooks/demo_colab.ipynb) clona el repo, toma la clave de los Secrets de Colab y permite evaluar un CCAM propio o recorrer los caminos de error sin clave.

### Sin clave: modo simulado

```bash
python -m src.motor consultas/01_version_software.json --simulado valido
python -m src.motor consultas/01_version_software.json --simulado invalido     # reintento y error estructurado
python -m src.motor consultas/01_version_software.json --simulado sin_conexion # error de API
python -m src.motor consultas/extra/entrada_invalida.json --simulado valido   # entrada inválida
```

## Contrato de datos

**Entrada:** `id_ccam` (patrón `CCAM-AAAA-NNN`), `tipo_cambio` (Enum), `area_solicitante` (Enum), `sistema_afectado` (3 a 120 caracteres), `descripcion` (30 a 2000 caracteres).

**Salida:** `fuera_de_alcance` (bool), `impacto_gxp` (Enum: sin_impacto, menor, mayor, critico), `requiere_revalidacion` (bool), `justificacion` (40 a 1200 caracteres), `fundamento` (SOPs con patrón `SOP-XX-000` que deben existir en el catálogo), `tareas` (con área responsable en Enum), `confianza` (0 a 1), `estado` (fijo `BORRADOR_PENDIENTE_QA`).

**Reglas cruzadas:** dentro de alcance exige impacto y al menos un SOP; impacto mayor o crítico exige al menos una tarea; revalidación es incompatible con "sin impacto"; fuera de alcance exige impacto nulo, sin tareas y sin revalidación.

## Decisiones

- **Claude Haiku 5.5** por costo: con unos 150 CCAM por mes, el costo mensual es de centavos de dólar. Sonnet 5.5 queda para comparar calidad en la PE6.
- **Sin temperatura:** desde la versión 2026-10-21 de la API, Claude no acepta `temperature`. La consistencia se controla con el contrato, el catálogo cerrado de SOPs y el reintento, y se medirá con evals en la PE6.
- **Proveedor intercambiable:** cambiar de modelo o de proveedor es cambiar `.env`; el resto del código no se toca.
- **Una sola fuente de verdad:** el PDF de cada entrega se arma solo desde la carpeta de una corrida, con manifiesto y hashes.
- **Registro de ejecuciones:** cada evaluación deja una línea en `logs/ejecuciones.jsonl` con `trace_id`, versión del prompt, resultado, tokens, costo y latencia (sin el texto del CCAM).
