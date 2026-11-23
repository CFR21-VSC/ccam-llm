# Correcciones de la devolución de la PE3 — 2026-11-23 12:41

Corpus congelado: `845258f96c8ae1dd…` (coincide con evals/corpus_congelado.json: ✓).

## M-1 · Fragmentado A y B

| | A | B |
|---|---|---|
| Tope (tokens) | 400 | 1000 |
| Solapamiento | 0.1 | 0.1 |
| Fragmentos | 25 | 11 |
| Tokens mín. | 69 | 282 |
| Tokens mediana | 290 | 472 |
| Tokens máx. | 369 | 939 |
| Documentos en un solo fragmento | 2 | 9 |

Método (igual en A y B): estructural: cada sección numerada (## y ###) es una unidad; las unidades seguidas del mismo documento se juntan mientras entren en el tope; una sección que no entra se parte por párrafo, después por línea y al final por caracteres. Solapamiento: el fragmento repite el último 10 % del contenido del fragmento anterior del mismo documento, empezando en borde de palabra y marcado con […]. Prefijo: CÓDIGO · Título · §primera sección [a §última sección], sacado del propio documento.

## M-2 · M-5 · Top-k por pregunta (configuración A, híbrida)

| Id | Tipo | Rol | Esperado | Puesto | @3 | @5 | Top 5 |
|---|---|---|---|---|---|---|---|
| P01 | normal_codigo | validaciones | SOP-EQ-005 §7.1 | 1 | ✓ | ✓ | SOP-EQ-005#A01 (§5.1,5.2,6,7,7.1,7.2); EXP-VAL-CROM-01#A00 (§1,2,3,3.1,3.2,3.3); SOP-EQ-005#A00 (§1,2,3,4,4.1,4.2,5); SOP-CC-001#A04 (§5.4); SOP-CC-001#A03 (§5.3) |
| P02 | normal_codigo | solicitante | SOP-VS-003 §3.2 | 1 | ✓ | ✓ | SOP-VS-003#A00 (§1,2,3,3.1,3.2,3.3); SOP-VS-003#A01 (§4,5,5.1,5.2,6); SOP-CC-001#A05 (§5.5,5.6); SOP-VS-002#A02 (§6.3,6.4,7); SOP-CC-001#A07 (§8) |
| P03 | normal | analista_qa | SOP-CC-001 §7 | 1 | ✓ | ✓ | SOP-CC-001#A06 (§5.7,5.8,6,7); SOP-CC-001#A07 (§8); SOP-CC-001#A01 (§3,4,5); SOP-CC-001#A02 (§5.1,5.2); INF-AUD-2026-03#A00 (§1,2,3,4) |
| P04 | normal | solicitante | SOP-DC-004 §3.2 | 1 | ✓ | ✓ | SOP-DC-004#A00 (§1,2,3,3.1,3.2,4,5); SOP-VS-003#A01 (§4,5,5.1,5.2,6); SOP-CC-001#A00 (§1,2); SOP-CC-001#A01 (§3,4,5); SOP-VS-003#A00 (§1,2,3,3.1,3.2,3.3) |
| P05 | normal | validaciones | SOP-EQ-005 §5.1 | 1 | ✓ | ✓ | SOP-EQ-005#A01 (§5.1,5.2,6,7,7.1,7.2); SOP-CC-001#A05 (§5.5,5.6); SOP-CC-001#A06 (§5.7,5.8,6,7); SOP-CC-001#A03 (§5.3); SOP-EQ-005#A00 (§1,2,3,4,4.1,4.2,5) |
| P06 | normal | analista_qa | SOP-VS-002 §5 | 1 | ✓ | ✓ | SOP-VS-002#A01 (§5,6,6.1,6.2); SOP-PR-006#A01 (§5); SOP-CC-001#A04 (§5.4); SOP-VS-002#A02 (§6.3,6.4,7); SOP-PR-006#A00 (§1,2,3,3.1,3.2,3.3,4) |
| P07 | sin_respuesta | analista_qa | — | — | ✓ | ✓ | SOP-PR-006#A00 (§1,2,3,3.1,3.2,3.3,4); SOP-PR-006#A01 (§5); INF-AUD-2026-03#A00 (§1,2,3,4); SOP-EQ-005#A00 (§1,2,3,4,4.1,4.2,5); SOP-VS-002#A01 (§5,6,6.1,6.2) |
| P08 | sin_respuesta | solicitante | — | — | ✓ | ✓ | SOP-CC-001#A07 (§8); SOP-CC-001#A00 (§1,2); SOP-DC-004#A00 (§1,2,3,3.1,3.2,4,5); SOP-CC-001#A01 (§3,4,5); SOP-CC-001#A06 (§5.7,5.8,6,7) |
| P09 | restringida | solicitante | — | — | ✓ | ✓ | SOP-CC-001#A05 (§5.5,5.6); SOP-EQ-005#A01 (§5.1,5.2,6,7,7.1,7.2); SOP-CC-001#A00 (§1,2); SOP-AC-007#A00 (§1,2,3,3.1,3.2,4,5); SOP-DC-004#A01 (§6) |
| P10 | restringida | validaciones | — | — | ✓ | ✓ | SOP-DC-004#A01 (§6); SOP-DC-004#A00 (§1,2,3,3.1,3.2,4,5); SOP-CC-001#A03 (§5.3); EXP-VAL-CROM-01#A01 (§3.4,4,5); SOP-VS-002#A01 (§5,6,6.1,6.2) |

## M-5 · M-6 · Matriz de seguridad

Consultas desde roles sin permiso: 53 · fugas en resultados: 0 · fugas en el prompt: 0 · control positivo: ✓

| Documento | solicitante | analista_qa | validaciones | jefe_qa |
|---|---|---|---|---|
| INF-AUD-2026-03 | bloqueado: 0 fugas en 8 ✓ | ve: en el top 5 en 8 de 8 ✓ | bloqueado: 0 fugas en 8 ✓ | ve: en el top 5 en 8 de 8 ✓ |
| EXP-VAL-CROM-01 | bloqueado: 0 fugas en 8 ✓ | bloqueado: 0 fugas en 8 ✓ | ve: en el top 5 en 8 de 8 ✓ | ve: en el top 5 en 8 de 8 ✓ |
| HAL-INSP-2026-01 | bloqueado: 0 fugas en 7 ✓ | bloqueado: 0 fugas en 7 ✓ | bloqueado: 0 fugas en 7 ✓ | ve: en el top 5 en 7 de 7 ✓ |

## M-4 · Casos nuevos con el corpus congelado

Coincidencia con QA: 5/10 · sobreclasifica 1 · subclasifica 2 · USD 0.001226 por CCAM

| # | Caso | QA | Sistema | Revalidación QA/sistema | Fundamento |
|---|---|---|---|---|---|
| 201 | Actualizar el sistema operativo de los servidores del LIMS de Windows  | menor | mayor ✗ | no/sí | SOP-VS-002 §3, SOP-VS-002 §5, SOP-CC-001 §5.1, SOP-CC-001 §5.7 |
| 202 | En el instructivo de limpieza de la línea 2, bajar el tiempo de contac | mayor | mayor | sí/sí | SOP-CC-001 §5.4, SOP-CC-001 §5.7, SOP-DC-004 §3.1 |
| 203 | Reemplazar el filtro HEPA del área de pesada por uno idéntico (mismo f | fuera_de_alcance | menor ✗ | no/no | SOP-CC-001 §5.3, SOP-CC-001 §5.1, SOP-CC-001 §5.7, SOP-EQ-005 §3 |
| 204 | Agregar en el LIMS el cálculo automático de uniformidad de contenido,  | critico | mayor ✗ | sí/sí | SOP-CC-001 §5.1, SOP-CC-001 §5.7, SOP-VS-002 §6.2, SOP-VS-002 §6.3 |
| 205 | Cambiar el proveedor de las cajas de cartón corrugado de transporte (e | menor | menor | no/no | SOP-CC-001 §5.3, SOP-CC-001 §5.7, SOP-PR-006 §3.3, SOP-AC-007 §4 |
| 206 | En la granulación húmeda del Analgésico X 500 mg, cambiar el orden de  | mayor | requiere_humano ✗ | sí/no | SOP-CC-001 §5.1, SOP-CC-001 §5.8 |
| 207 | Cambiar la política de contraseñas de los sistemas GxP: vencimiento de | mayor | mayor | no/no | SOP-CC-001 §5.7, SOP-CC-001 §5.1, SOP-VS-002 §6.2, SOP-VS-002 §6.1 |
| 208 | Mover el depósito de material de empaque secundario a otro sector del  | requiere_humano | requiere_humano | no/no | SOP-CC-001 §5.2, SOP-AC-007 §5 |
| 209 | Agrandar la letra del prospecto para mejorar la legibilidad, sin cambi | mayor | menor ✗ | no/no | SOP-CC-001 §5.1, SOP-CC-001 §5.7, SOP-AC-007 §3.1, SOP-AC-007 §5 |
| 210 | Actualizar el software de los registradores de temperatura de las hela | mayor | mayor | sí/sí | SOP-CC-001 §5.7, SOP-VS-002 §6.2, SOP-VS-002 §5, SOP-VS-002 §6.3 |

## M-3 · Objeto completo de responder()

Ver `ejemplo_responder.json`.
