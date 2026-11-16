# Registro de decisiones

Una fila por decisión de diseño, con su porqué. No se borran: si una decisión cambia, se agrega una nueva que la reemplaza. Sirve para el capítulo de decisiones de cada PDF y para la defensa de la PE10.

| ID | Fecha | Decisión | Por qué | Alternativa descartada |
| --- | --- | --- | --- | --- |
| D-01 | 2026-10-23 | Caso: evaluación de impacto de control de cambios GxP | Proceso real, medible y entrevistable; cumple los 7 requisitos del caso viable | Cadena de frío; caso no regulado |
| D-02 | 2026-10-23 | El agente propone y QA aprueba, sobre un sistema de cambios simulado | Riesgo regulatorio de IA generativa en decisiones GMP; sin acceso al QMS real | Agente autónomo integrado al QMS productivo |
| D-03 | 2026-10-26 | Texto libre solo para lo que lee una persona; lo demás cerrado | Hallazgo 1 de la PE1: el criterio de evaluación no es uniforme | Contrato con campos de texto libre |
| D-04 | 2026-10-26 | Catálogo cerrado de SOPs en el prompt y validado en el contrato | Evitar fuentes inventadas antes de tener RAG (riesgo R3) | Confiar en el SOP que cite el modelo |
| D-05 | 2026-10-26 | Claude Haiku 5.5 como modelo base | Con 150 CCAM por mes el costo es de centavos; la calidad se compara en la PE6 | Sonnet 5.5 desde el inicio |
| D-06 | 2026-10-26 | Salida estructurada con `tools` + `tool_choice` y validación local con Pydantic | El esquema orienta la forma, no garantiza el contenido ni las reglas cruzadas | Pedir JSON en texto libre |
| D-07 | 2026-10-26 | Un solo reintento, devolviendo al modelo los campos que fallaron | Corrige errores puntuales sin duplicar costo sin límite | Sin reintento; reintentos ilimitados |
| D-08 | 2026-10-26 | Proveedor intercambiable (Anthropic, OpenAI, simulado) | RFC-000 principio 4; habilita el A/B de la PE6 y un modelo self-hosted a futuro | Código atado a un proveedor |
| D-09 | 2026-10-26 | Sin `temperature` en Claude | La API 2026-10-21 la eliminó (error 400); la consistencia se controla con contrato, catálogo y reintento | Fijar una versión vieja de la API |
| D-10 | 2026-10-26 | Log JSONL con `trace_id` y `version_prompt`, sin el texto del CCAM | Trazabilidad tipo audit trail sin duplicar información sensible | Solo imprimir en pantalla |
| D-11 | 2026-10-26 | Redis para caché recién en la PE8 | La consigna lo ubica en despliegue; agregarlo antes complica correr desde un clon limpio | Caché con Redis en la PE2 |
| D-12 | 2026-10-30 | Demo para terceros en Colab con la clave en Secrets | Es el entorno que usa el curso; cada persona usa su propia clave | URL pública antes de la PE8 |
| D-13 | 2026-10-30 | Techo de salida de 3.000 tokens (antes 1.500) | En la primera corrida real Haiku usó 1.160 tokens de salida en un CCAM crítico con 7 tareas: margen de 23 %. Solo se paga lo que se usa, y un corte por largo gasta un reintento | Dejar 1.500 y reintentar cuando se corta |
| D-14 | 2026-11-16 | Una sola corrida por entrega (`scripts.corrida`) como fuente de verdad, con manifiesto y hashes | Devolución de la PE2: la ejecución exitosa y la tabla salían de dos llamadas distintas y no coincidían | Mantener `medir` y `evidencia` como scripts separados |
| D-15 | 2026-11-16 | Integración continua en GitHub Actions, sin clave, con Python 3.11 y 3.12 | Devolución de la PE2: demostrar que el repo se reproduce desde un clon limpio, en cada push | Probarlo a mano una vez por entrega |
| D-16 | 2026-11-16 | Los tags no se mueven: `pe2` queda en el commit evaluado (`c92b40d`); las correcciones van en `pe2.1` o en la entrega siguiente | Un tag es un registro de lo entregado, como un documento aprobado | Mover `pe2` al commit corregido |
| D-17 | 2026-11-16 | Regla R-QA-01: ante la duda real, el nivel más alto, pidiendo el dato que falta; se incorpora al prompt en la PE3 | Acordada con Federico al cerrar el caso 14; no habilita subir el nivel cuando el dato está (H-01) | Clasificar siempre en el nivel técnico más probable |
| D-18 | 2026-11-16 | 10 casos nuevos (06 a 15) clasificados por Federico, con justificación de QA en cada archivo | Devolución de la PE2: medir la frontera mayor/crítico con más casos; la justificación sirve al juez LLM de la PE6 | Que Claude proponga la clasificación esperada |
