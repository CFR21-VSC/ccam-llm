# Corrida PE3 — 2026-11-16 11:54

Todo sale de los archivos de esta carpeta.

## 1. Recall@k por configuración de fragmentado

Consultas medidas: 14 (6 preguntas normales + 8 con códigos exactos). Acierto = el documento y la sección esperados están en los k primeros fragmentos.

| Config | Fragmentos | Tokens de contexto @5 | Vectorial @3 | @5 | BM25 @3 | @5 | Híbrida @3 | @5 |
|---|---|---|---|---|---|---|---|---|
| A (~400 tokens) | 23 | 1452 | 71% | 86% | 100% | 100% | 100% | 100% |
| B (~1000 tokens) | 11 | 2940 | 86% | 93% | 100% | 100% | 100% | 100% |

## 2. Híbrida acierta y vectorial falla (config A, k = 3)

| Id | Consulta | Esperado | Top 3 vectorial | Top 3 híbrida |
|---|---|---|---|---|
| P04 | Si corrijo un error de tipeo en un instructivo, ¿tengo que capacitar al personal? | SOP-DC-004 §3.2 | SOP-EQ-005#A00, SOP-PR-006#A01, SOP-CC-001#A02 | SOP-DC-004#A00, SOP-VS-003#A01, SOP-CC-001#A01 |
| C02 | CAPA-2026-014 | INF-AUD-2026-03 §2 | EXP-VAL-CROM-01#A01, INF-AUD-2026-03#A01, EXP-VAL-CROM-01#A00 | INF-AUD-2026-03#A01, INF-AUD-2026-03#A00, EXP-VAL-CROM-01#A01 |
| C03 | CAPA-2026-041 | INF-AUD-2026-03 §3 | EXP-VAL-CROM-01#A01, INF-AUD-2026-03#A01, EXP-VAL-CROM-01#A00 | INF-AUD-2026-03#A01, INF-AUD-2026-03#A00, EXP-VAL-CROM-01#A01 |
| C07 | R-QA-01 | SOP-CC-001 §5.8 | EXP-VAL-CROM-01#A01, EXP-VAL-CROM-01#A00, SOP-EQ-005#A01 | SOP-CC-001#A04, EXP-VAL-CROM-01#A01, EXP-VAL-CROM-01#A00 |

Al revés (vectorial acierta y la híbrida falla): ninguna.

## 3. Permisos

| Usuario | Documentos que ve |
|---|---|
| u_solicitante_prod | 7: SOP-AC-007, SOP-CC-001, SOP-DC-004, SOP-EQ-005, SOP-PR-006, SOP-VS-002, SOP-VS-003 |
| u_analista_qa | 8: INF-AUD-2026-03, SOP-AC-007, SOP-CC-001, SOP-DC-004, SOP-EQ-005, SOP-PR-006, SOP-VS-002, SOP-VS-003 |
| u_validaciones | 8: EXP-VAL-CROM-01, SOP-AC-007, SOP-CC-001, SOP-DC-004, SOP-EQ-005, SOP-PR-006, SOP-VS-002, SOP-VS-003 |
| u_jefe_qa | 10: EXP-VAL-CROM-01, HAL-INSP-2026-01, INF-AUD-2026-03, SOP-AC-007, SOP-CC-001, SOP-DC-004, SOP-EQ-005, SOP-PR-006, SOP-VS-002, SOP-VS-003 |

Frases testigo: 12/12 combinaciones documento × usuario correctas (con permiso: aparece en resultados y prompt; sin permiso: en ninguno). Usuario desconocido recibe 0 fragmentos.

| Documento | Frase | Usuario | ¿Permiso? | ¿En resultados? | ¿En prompt? |
|---|---|---|---|---|---|
| INF-AUD-2026-03 | TESTIGO-AUD-7731 | u_solicitante_prod | No | No | No |
| INF-AUD-2026-03 | TESTIGO-AUD-7731 | u_analista_qa | Sí | Sí | Sí |
| INF-AUD-2026-03 | TESTIGO-AUD-7731 | u_validaciones | No | No | No |
| INF-AUD-2026-03 | TESTIGO-AUD-7731 | u_jefe_qa | Sí | Sí | Sí |
| EXP-VAL-CROM-01 | TESTIGO-VAL-4408 | u_solicitante_prod | No | No | No |
| EXP-VAL-CROM-01 | TESTIGO-VAL-4408 | u_analista_qa | No | No | No |
| EXP-VAL-CROM-01 | TESTIGO-VAL-4408 | u_validaciones | Sí | Sí | Sí |
| EXP-VAL-CROM-01 | TESTIGO-VAL-4408 | u_jefe_qa | Sí | Sí | Sí |
| HAL-INSP-2026-01 | TESTIGO-INSP-2290 | u_solicitante_prod | No | No | No |
| HAL-INSP-2026-01 | TESTIGO-INSP-2290 | u_analista_qa | No | No | No |
| HAL-INSP-2026-01 | TESTIGO-INSP-2290 | u_validaciones | No | No | No |
| HAL-INSP-2026-01 | TESTIGO-INSP-2290 | u_jefe_qa | Sí | Sí | Sí |

## 4. Las 10 preguntas

| Id | Tipo | Usuario | requiere_humano (esperado) | Citas | Esperado | Similitud máx. | ¿Correcta? |
|---|---|---|---|---|---|---|---|
| P01 | normal_codigo | u_validaciones | False (False) | SOP-EQ-005 §7.1 | SOP-EQ-005 §7.1 | 0.6612 | Sí |
| P02 | normal_codigo | u_solicitante_prod | False (False) | SOP-VS-003 §3.2 | SOP-VS-003 §3.2 | 0.6678 | Sí |
| P03 | normal | u_analista_qa | False (False) | SOP-CC-001 §7 | SOP-CC-001 §7 | 0.5974 | Sí |
| P04 | normal | u_solicitante_prod | False (False) | SOP-DC-004 §3.2, SOP-DC-004 §3.1 | SOP-DC-004 §3.2 | 0.5009 | Sí |
| P05 | normal | u_validaciones | False (False) | SOP-EQ-005 §5.1 | SOP-EQ-005 §5.1 | 0.4463 | Sí |
| P06 | normal | u_analista_qa | False (False) | SOP-VS-002 §5 | SOP-VS-002 §5 | 0.5923 | Sí |
| P07 | sin_respuesta | u_analista_qa | True (True) | - | - | 0.442 | Sí |
| P08 | sin_respuesta | u_solicitante_prod | True (True) | - | - | 0.2378 | Sí |
| P09 | restringida | u_solicitante_prod | True (True) | - | - | 0.5361 | Sí |
| P10 | restringida | u_validaciones | True (True) | - | - | 0.5721 | Sí |

Correctas: 10/10.

## 5. Los 15 CCAM con RAG (u_analista_qa)

Armada leyendo los `caso_NN.json` de esta misma carpeta: cada fila es la ejecución de su `caso_NN.txt`.

| # | Consulta | Grupo | ¿Validó? | Intentos | Tokens entrada / salida | Costo USD | Latencia ms | Confianza | Propuesto | Esperado QA | Coincide |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | Actualización de versión del software cromatográfico | pe2_originales | Sí | 1 | 6557 / 1118 | 0.001215 | 4516 | 0.8 | mayor | mayor | Sí |
| 02 | Nuevo diseño del estuche secundario | pe2_originales | Sí | 1 | 7004 / 1046 | 0.001223 | 4549 | 0.7 | menor | mayor | No |
| 03 | Cambio de proveedor de un excipiente | pe2_originales | Sí | 1 | 6046 / 1113 | 0.001161 | 5108 | 0.85 | mayor | mayor | Sí |
| 04 | Consulta confusa: impresora | pe2_originales | Sí | 1 | 6756 / 434 | 0.000893 | 4197 | 0.3 | requiere_humano | menor | No |
| 05 | Consulta fuera de tema | pe2_originales | Sí | 1 | 5969 / 344 | 0.000769 | 1968 | 0.9 | fuera_de_alcance | fuera_de_alcance | Sí |
| 06 | Parche del LIMS validado por el proveedor | anclas | Sí | 1 | 6876 / 922 | 0.001149 | 3906 | 0.7 | menor | menor | Sí |
| 07 | Nueva firma electrónica en la liberación de lotes | frontera | Sí | 1 | 6784 / 1136 | 0.001246 | 4686 | 0.9 | critico | critico | Sí |
| 08 | Desactivar el audit trail del cromatográfico | frontera | Sí | 1 | 6178 / 961 | 0.001098 | 4272 | 0.9 | critico | critico | Sí |
| 09 | Perfil de solo consulta en el LIMS | anclas | Sí | 1 | 6864 / 653 | 0.001013 | 2787 | 0.85 | menor | menor | Sí |
| 10 | Reemplazo de balanza analítica que falló | frontera | Sí | 1 | 6992 / 1159 | 0.001279 | 4931 | 0.8 | mayor | mayor | Sí |
| 11 | Traslado de la cámara de estabilidad | frontera | Sí | 1 | 7164 / 1000 | 0.001216 | 4299 | 0.85 | critico | mayor | No |
| 12 | Errores de tipeo en un instructivo de limpieza | anclas | Sí | 1 | 6180 / 702 | 0.000969 | 3235 | 0.8 | menor | menor | Sí |
| 13 | Comprimidora fuera del rango validado | frontera | Sí | 1 | 6979 / 922 | 0.001159 | 4212 | 0.9 | critico | critico | Sí |
| 14 | Redondeo de la valoración en el certificado | frontera | Sí | 1 | 6504 / 882 | 0.001091 | 3870 | 0.85 | mayor | mayor | Sí |
| 15 | Antivirus en PCs administrativas sin sistemas GxP | anclas | Sí | 1 | 6303 / 411 | 0.000836 | 2312 | 0.8 | fuera_de_alcance | sin_impacto | No |
| | **Promedio de las válidas** | | **15/15** | | **6610 / 854** | **0.001088** | **3923** | | | | **11/15 (73%)** |

## Coincidencia con QA

| Corte | Aciertos |
|---|---|
| Total | 11/15 (73%) |
| Grupo: pe2_originales | 3/5 (60%) |
| Grupo: anclas | 3/4 (75%) |
| Grupo: frontera | 5/6 (83%) |
| Nivel esperado: sin_impacto | 0/1 (0%) |
| Nivel esperado: menor | 3/4 (75%) |
| Nivel esperado: mayor | 4/6 (67%) |
| Nivel esperado: critico | 3/3 (100%) |
| Nivel esperado: fuera_de_alcance | 1/1 (100%) |

Discrepancias de nivel: 1 sobreclasificaciones y 1 subclasificaciones.

## Comparación con la PE1

- Latencia promedio 3923 ms (peor caso 5108 ms) contra la meta de la HU-01 (< 30000 ms; deseable < 20000 ms): **cumple**.
- Coincidencia con QA: 11/15 (73%) contra la meta del KPI técnico (≥ 90%). Es indicativa; la medición formal es la PE6 con golden dataset.

## 6. PE2 (catálogo) contra PE3 (RAG)

| | PE2 (corrida_20261116_1116) | PE3 |
|---|---|---|
| Coincidencia con QA | 11/15 | 11/15 |
| Tokens de entrada promedio | 2463 | 6610 |
| Costo promedio USD | 0.000680 | 0.001088 |
| Latencia promedio ms | 3971 | 3923 |
| Sobre / subclasificaciones | 4 / 0 | 1 / 1 |

| # | Esperado QA | PE2 | PE3 |
|---|---|---|---|
| 01 | mayor | critico | mayor |
| 02 | mayor | mayor | menor |
| 03 | mayor | mayor | mayor |
| 04 | menor | menor | requiere_humano |
| 05 | fuera_de_alcance | fuera_de_alcance | fuera_de_alcance |
| 06 | menor | mayor | menor |
| 07 | critico | critico | critico |
| 08 | critico | critico | critico |
| 09 | menor | mayor | menor |
| 10 | mayor | mayor | mayor |
| 11 | mayor | critico | critico |
| 12 | menor | menor | menor |
| 13 | critico | critico | critico |
| 14 | mayor | mayor | mayor |
| 15 | sin_impacto | sin_impacto | fuera_de_alcance |
