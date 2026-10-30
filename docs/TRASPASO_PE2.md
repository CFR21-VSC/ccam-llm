# Traspaso PE2: de Claude Code a Claude (app)

Escrito por Claude Code el 2026-10-30 al cerrar la corrida real. Lo que sigue es para la sesión de Claude en la app que arma el PDF `FDE_PE2_Bongiovanni_Federico.pdf`. Leer antes `CLAUDE.md`, `docs/ESTADO.md` y `docs/DECISIONES.md`.

## 1. Dónde está todo

- **Repo público:** <https://github.com/CFR21-VSC/ccam-llm>, rama `main`. El nombre de la consigna era `fde-<tu-caso>`; el repo se llama `ccam-llm` porque Federico ya lo tenía creado en la cuenta CFR21-VSC.
- **Carpeta local:** `C:\proyectos\ccam-llm`. Las copias viejas (`C:\proyectos\Agente LLm para CCAM´s` y `OneDrive\Escritorio\FDE\fde-control-cambios`) ya no se usan.
- **Tag `pe2`:** todavía **no** está puesto. Se pone cuando Federico apruebe el PDF (ver punto 6).
- **Clave:** está en `.env`, que git ignora. Se verificó que ningún archivo del repo la contiene. No pedirla ni mencionarla en el PDF más allá de "la clave vive en `.env`, fuera del repo".

## 2. Resultados reales (2026-10-30, `claude-haiku-5-5`)

Fuente: `resultados/medicion_20261030_1626.md` y `.json`.

| # | Consulta | Tipo | ¿Validó? | Intentos | Tokens entrada / salida | Costo USD | Latencia ms | Propuesto | Esperado QA | Coincide | Confianza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Actualización del software cromatográfico | normal | Sí | 1 | 2497 / 1162 | 0,000831 | 5053 | crítico | mayor | **No** | 0,7 |
| 2 | Nuevo diseño del estuche secundario | normal | Sí | 1 | 2485 / 953 | 0,000725 | 4621 | mayor | mayor | Sí | 0,8 |
| 3 | Cambio de proveedor de un excipiente | normal | Sí | 1 | 2481 / 1007 | 0,000752 | 4583 | mayor | mayor | Sí | 0,6 |
| 4 | Consulta confusa: impresora | confusa | Sí | 1 | 2422 / 674 | 0,000579 | 3642 | menor | menor | Sí | 0,4 |
| 5 | Consulta fuera de tema | fuera de tema | Sí | 1 | 2428 / 292 | 0,000389 | 1807 | fuera de alcance | fuera de alcance | Sí | 0,9 |
| | **Promedio** | | **5/5** | | **2463 / 818** | **0,000655** | **3941** | | | **4/5 (80 %)** | |

Comparación con los KPIs de la PE1:

- **HU-01 (< 30 s, deseable < 20 s):** cumple con amplitud, con 3,9 s de promedio y 5,1 s el peor caso.
- **KPI técnico (coincidencia con QA ≥ 90 %):** 80 % preliminar, por debajo de la meta. Con 5 casos es una señal, no una medición; la formal es la PE6, con golden dataset y juez.
- **Costo:** USD 0,000655 por CCAM. Con 150 CCAM por mes da unos USD 0,10 por mes.

Evidencia de terminal (`resultados/evidencia_*.txt`), una corrida aparte del mismo día:

| Archivo | Qué muestra | Resultado |
| --- | --- | --- |
| `evidencia_exito.txt` | CCAM 01 contra Claude real, con la ficha completa | VALIDADO, 1 intento, 2497/1160 tokens, USD 0,000830, 5470 ms |
| `evidencia_reintento.txt` | Salida inválida forzada con el simulador: campo que falló, reintento y error estructurado | `salida_invalida` tras 2 intentos |
| `evidencia_error_api.txt` | Llamada real a Anthropic con una clave inventada | `api_autenticacion` (401 capturado, sin traceback) |
| `evidencia_entrada.txt` | Entrada que no cumple el contrato | `entrada_invalida`, sin llamar al modelo |

## 3. Lo que se detectó como erróneo o mejorable

### En el comportamiento del modelo (van al PDF como hallazgos)

| ID | Hallazgo | Evidencia | Tratamiento |
| --- | --- | --- | --- |
| H-01 | **Sobreclasificación del CCAM 01.** Haiku propuso *crítico*; el criterio de QA de Federico es *mayor*. El modelo fue más estricto que QA: razonó que el software controla los 4 HPLC y la base de resultados que respalda la liberación de producto. Fue consistente: dio *crítico* en las dos corridas, con confianza 0,8 y 0,7. | `medicion_20261030_1626.json` fila 1; `evidencia_exito.txt` | El `esperado` **no se cambia**: el criterio es el de QA. Alimenta el riesgo R3 y la PE6: ver si el modelo sube el nivel sistemáticamente cuando aparecen datos de liberación, y si conviene sumar al prompt (o, desde la PE3, a los SOPs) la diferencia entre mayor y crítico para una actualización de versión con validación del proveedor. Es un error "del lado seguro" (sobreclasificar, no subclasificar), pero igual cuesta: más trabajo de validación del necesario. |
| H-02 | **SOP citado en una tarea que no está en el fundamento.** Una tarea del CCAM 01 dice "según SOP-DC-004", pero el fundamento lista solo SOP-CC-001, SOP-VS-002, SOP-VS-003 y SOP-EQ-005. | `evidencia_exito.txt`, tarea 7 | El contrato valida los códigos del `fundamento` contra el catálogo, pero no el texto libre de las tareas. Mejora para la PE3: exigir que todo SOP mencionado en una tarea figure en el fundamento (regla cruzada nueva). |
| H-03 | **Error de redacción.** "los métodos analíticos validados en las 3.6". | `evidencia_exito.txt`, tarea 6 | Menor. Lo corrige QA al revisar el borrador; no amerita regla. |
| H-04 | **La confianza acompaña bien a la ambigüedad.** La consulta confusa (04) bajó a 0,4 y la fuera de tema (05) quedó en 0,9. | `medicion_20261030_1626.json` | Es un hallazgo positivo: la confianza sirve como señal para priorizar la revisión de QA. |

### En la medición y la configuración (corregidos o anotados)

| ID | Hallazgo | Tratamiento |
| --- | --- | --- |
| H-05 | **El techo de 1.500 tokens de salida quedaba justo.** El CCAM 01 usó 1.160 a 1.162 (margen de 23 %). | **Corregido:** el techo pasó a 3.000 (decisión D-13). Solo se paga lo que se usa; un corte por largo gastaría un reintento. La medición ya corrió con 3.000. |
| H-06 | **`scripts.medir` no guarda la ficha completa.** Solo guarda impacto, tokens, costo y latencia; la justificación, los SOPs y las tareas de las consultas 2 a 5 no quedaron registradas. La única ficha completa es la del CCAM 01, en `evidencia_exito.txt`. | **Pendiente**, para Claude Code: que `medir` guarde también la propuesta completa en el `.json`. Para el PDF alcanza con la ficha del CCAM 01 como ejemplo de salida validada. |
| H-07 | **El caso `consultas/extra/trampa_sop_inexistente.json` no se corrió contra el modelo real.** | Opcional. El catálogo cerrado se valida en las pruebas sin tokens; si se quiere evidencia real, correrlo antes del tag. |

### En el repo y el entorno (corregidos en esta sesión)

| ID | Hallazgo | Tratamiento |
| --- | --- | --- |
| H-08 | **Había dos copias del proyecto desfasadas.** La de `C:\proyectos` tenía código del 26/10 (15 pruebas, sin el arreglo de "sin clave"); la de OneDrive tenía el código del 30/10, pero los docs más nuevos estaban sueltos en la carpeta de proyectos. | Unificadas en `C:\proyectos\ccam-llm`. |
| H-09 | **La ruta tenía espacios y el carácter `´`** (`Agente LLm para CCAM´s`), que la terminal mostraba roto. | Repo movido a `C:\proyectos\ccam-llm`. |
| H-10 | **A la PC le faltaba la librería `anthropic`.** La prueba "sin clave" fallaba con un error de configuración engañoso. | Entorno `.venv` creado con `requirements.txt`; 16 pruebas en verde. |
| H-11 | **El `.gitignore` solo cubría `.env` exacto.** | Ahora cubre `.env.*` y deja pasar solo `.env.example`. |
| H-12 | **El README y la demo de Colab apuntaban a `<usuario>/fde-control-cambios`.** | Apuntan a `CFR21-VSC/ccam-llm`. |
| H-13 | **Repo público.** | No hay claves en el repo (verificado buscando la clave real en todos los archivos). Recomendación pendiente para Federico: activar *Secret scanning* y *Push protection* en GitHub y ponerle un límite de gasto mensual a la clave en la consola de Anthropic. |

## 4. Qué tiene que tener el PDF

Consigna del módulo 2 (págs. 34 y 35): se entrega el **repo con tag `pe2`** y el **PDF `FDE_PE2_Bongiovanni_Federico.pdf`**. La rúbrica es sobre 100 y se aprueba con 70.

| Criterio | Peso | Qué mostrar | De dónde sale |
| --- | --- | --- | --- |
| Contrato de datos | 25 % | `Entrada` y `Salida` con sus reglas (Enums, patrón `CCAM-AAAA-NNN`, rangos y largos, `estado` fijo `BORRADOR_PENDIENTE_QA`) y las 4 reglas cruzadas. Por qué casi nada es texto libre (D-03) y por qué el catálogo es cerrado (D-04). | `src/contrato.py`, README sección "Contrato de datos" |
| Llamada real y salida validada | 25 % | El prompt como plantilla aparte (`prompts/`), la salida estructurada con `tools` (D-06), la clave en `.env` y la ficha real del CCAM 01 validada. | `prompts/`, `evidencia_exito.txt` |
| Medición real | 20 % | La tabla del punto 2 completa, con la comparación contra la HU-01 y el KPI técnico, y el hallazgo H-01 explicado: el 80 % es honesto y se mejora en la PE6. | `medicion_20261030_1626.md` |
| Manejo de errores | 15 % | Los 4 archivos de evidencia: campo que falló con su ruta, reintento, error estructurado, error real de API 401 y entrada inválida. Que nunca sale un traceback. | `resultados/evidencia_*.txt` |
| Repo ordenado y seguro | 15 % | El link al repo, el tag `pe2`, el `.gitignore`, `.env.example` sin valores y la aclaración de que no hay claves subidas. | README, H-11, H-13 |

Además conviene sumar:

- **Las decisiones D-01 a D-13** (`docs/DECISIONES.md`), sobre todo D-05 (Haiku por costo), D-09 (sin `temperature`) y D-13 (techo de 3.000).
- **Temperatura:** la consigna la menciona como factor de variación (Coder Tip de la pág. 21 del módulo 2), pero Claude la rechaza desde la API 2026-10-21. La consistencia se controla con el contrato, el catálogo cerrado, las reglas cruzadas y el reintento, y se mide en la PE6.
- **Los hallazgos H-01 a H-04** como sección propia ("Qué aprendimos de la corrida real") y su vínculo con R3 y la PE6.
- **El link a la demo de Colab:** `notebooks/demo_colab.ipynb` en el repo.
- **Próximos pasos:** PE3 con RAG sobre los SOPs (reemplaza el catálogo en el prompt y habilita la regla de H-02).

Estilo: español rioplatense, voz de Federico (especialista en QA/CSV, no programador), con el equivalente GxP cuando ayude. Datos ficticios: aclararlo en el PDF.

## 5. Lo que NO hay que hacer

- No cambiar el `esperado` del CCAM 01: el criterio de QA es *mayor* (confirmado por Federico el 2026-10-30).
- No inventar números: todos salen de `resultados/`.
- No incluir la clave, ni parcial, en el PDF ni en capturas.

## 6. Cierre (lo hace Claude Code cuando el PDF esté aprobado)

1. Si se decide resolver H-06 o H-07 antes de la entrega, hacerlo y volver a correr la medición.
2. Verificar que ningún archivo del repo contenga la clave.
3. `git tag pe2` y `git push origin pe2`.
4. Actualizar `docs/ESTADO.md`: PE2 cerrada, link del PDF entregado.
