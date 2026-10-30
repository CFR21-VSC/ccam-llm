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
