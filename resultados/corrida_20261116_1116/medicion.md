# Medición — 2026-11-16 11:18 — modelo claude-haiku-5-5

Armada leyendo los `caso_NN.json` de esta misma carpeta: cada fila es la ejecución de su `caso_NN.txt`.

| # | Consulta | Grupo | ¿Validó? | Intentos | Tokens entrada / salida | Costo USD | Latencia ms | Confianza | Propuesto | Esperado QA | Coincide |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | Actualización de versión del software cromatográfico | pe2_originales | Sí | 1 | 2497 / 1115 | 0.000807 | 5223 | 0.8 | critico | mayor | No |
| 02 | Nuevo diseño del estuche secundario | pe2_originales | Sí | 1 | 2485 / 987 | 0.000742 | 4448 | 0.75 | mayor | mayor | Sí |
| 03 | Cambio de proveedor de un excipiente | pe2_originales | Sí | 1 | 2481 / 1025 | 0.000761 | 4542 | 0.7 | mayor | mayor | Sí |
| 04 | Consulta confusa: impresora | pe2_originales | Sí | 1 | 2422 / 739 | 0.000612 | 3583 | 0.4 | menor | menor | Sí |
| 05 | Consulta fuera de tema | pe2_originales | Sí | 1 | 2428 / 293 | 0.000389 | 1789 | 0.9 | fuera_de_alcance | fuera_de_alcance | Sí |
| 06 | Parche del LIMS validado por el proveedor | anclas | Sí | 1 | 2474 / 923 | 0.000709 | 4024 | 0.6 | mayor | menor | No |
| 07 | Nueva firma electrónica en la liberación de lotes | frontera | Sí | 1 | 2471 / 970 | 0.000732 | 4068 | 0.8 | critico | critico | Sí |
| 08 | Desactivar el audit trail del cromatográfico | frontera | Sí | 1 | 2459 / 977 | 0.000734 | 4339 | 0.8 | critico | critico | Sí |
| 09 | Perfil de solo consulta en el LIMS | anclas | Sí | 1 | 2440 / 792 | 0.000640 | 3763 | 0.7 | mayor | menor | No |
| 10 | Reemplazo de balanza analítica que falló | frontera | Sí | 1 | 2456 / 949 | 0.000720 | 4349 | 0.8 | mayor | mayor | Sí |
| 11 | Traslado de la cámara de estabilidad | frontera | Sí | 1 | 2481 / 1133 | 0.000815 | 5022 | 0.7 | critico | mayor | No |
| 12 | Errores de tipeo en un instructivo de limpieza | anclas | Sí | 1 | 2468 / 607 | 0.000550 | 2790 | 0.9 | menor | menor | Sí |
| 13 | Comprimidora fuera del rango validado | frontera | Sí | 1 | 2468 / 1019 | 0.000756 | 4661 | 0.8 | critico | critico | Sí |
| 14 | Redondeo de la valoración en el certificado | frontera | Sí | 1 | 2457 / 890 | 0.000691 | 4155 | 0.75 | mayor | mayor | Sí |
| 15 | Antivirus en PCs administrativas sin sistemas GxP | anclas | Sí | 1 | 2452 / 585 | 0.000538 | 2812 | 0.8 | sin_impacto | sin_impacto | Sí |
| | **Promedio de las válidas** | | **15/15** | | **2463 / 867** | **0.000680** | **3971** | | | | **11/15 (73%)** |

## Coincidencia con QA

| Corte | Aciertos |
|---|---|
| Total | 11/15 (73%) |
| Grupo: pe2_originales | 4/5 (80%) |
| Grupo: anclas | 2/4 (50%) |
| Grupo: frontera | 5/6 (83%) |
| Nivel esperado: sin_impacto | 1/1 (100%) |
| Nivel esperado: menor | 2/4 (50%) |
| Nivel esperado: mayor | 4/6 (67%) |
| Nivel esperado: critico | 3/3 (100%) |
| Nivel esperado: fuera_de_alcance | 1/1 (100%) |

Discrepancias de nivel: 4 sobreclasificaciones y 0 subclasificaciones.

## Comparación con la PE1

- Latencia promedio 3971 ms (peor caso 5223 ms) contra la meta de la HU-01 (< 30000 ms; deseable < 20000 ms): **cumple**.
- Coincidencia con QA: 11/15 (73%) contra la meta del KPI técnico (≥ 90%). Es indicativa; la medición formal es la PE6 con golden dataset.
