# Pedido: correcciones de la devolución de la PE2

Pedido para Claude Code, escrito desde la app de Claude el 2026-11-02. Leer antes `CLAUDE.md`, `docs/ESTADO.md` y `docs/DECISIONES.md`. Va **antes** de empezar la PE3, porque las correcciones dejan la base de evidencia que van a usar todas las entregas siguientes.

## La devolución del docente (resumen)

Puntos fuertes: contrato sólido, medición completa con caso confuso y fuera de tema, manejo de errores bien trazado y decisiones conectadas con los hallazgos.

Para mejorar:

1. Etiqueta inconsistente: aparece `pe21` en un lugar y `pe2` en otro.
2. `requirements.txt` no figura en la estructura del repo del PDF.
3. La ejecución exitosa (2497/1160 tokens, USD 0,000830) no coincide con la fila 1 de la tabla (2497/1162, USD 0,000831).
4. Transcripciones resumidas con «…»: quiere capturas completas.
5. Verificar que el repo se reproduce desde un clon limpio.
6. Una sola fuente de verdad para las métricas.
7. Antes de la PE6, medir con más casos la frontera entre impacto mayor y crítico.

## Diagnóstico

| # | Causa real | Corrección |
| --- | --- | --- |
| 1 | **El tag nunca se subió:** `git ls-remote --tags origin` no devuelve nada. Quedó pendiente "hasta aprobar el PDF". | Tarea 1 |
| 2 | Se sacó del árbol del PDF para ganar espacio. | En el PDF (lo hace la app) |
| 3 | `scripts.evidencia` hizo **otra** llamada real al CCAM 01, distinta de la de `scripts.medir`. Son dos corridas. | Tarea 2 |
| 4 | El PDF resume la ficha para entrar en 2 páginas. | Tarea 2 + anexo en el PDF |
| 5 | Nunca se probó desde un clon limpio en otra máquina. | Tarea 3 |
| 6 | Igual que el 3. | Tarea 2 |
| 7 | Solo 5 casos, uno solo en la frontera. | Tarea 4: 10 casos nuevos, ya clasificados por Federico |

## Tarea 1. Tag `pe2` en GitHub (ya)

El tag marca lo que se evaluó, así que va sobre el commit entregado, **no** sobre las correcciones:

```bash
git tag -a pe2 c92b40d -m "Pre-Entrega 2: motor LLM base y validación estructurada"
git push origin pe2
git ls-remote --tags origin      # tiene que aparecer refs/tags/pe2
```

Las correcciones de este pedido van en commits nuevos y quedan dentro de lo que se etiquete como `pe3`. Si Federico decide reenviar la PE2 corregida, se agrega `pe2.1` sobre el commit corregido y se documenta en `docs/DECISIONES.md` (nunca se mueve `pe2`).

## Tarea 2. Una sola corrida, una sola fuente de verdad

Reemplazar el par `scripts.medir` + `scripts.evidencia` por **un solo comando** que haga todo en la misma corrida y guarde todo junto:

```bash
python -m scripts.corrida
```

Comportamiento:

1. Crea `resultados/corrida_AAAAMMDD_HHMM/`.
2. Corre los casos de `consultas/0*.json` contra el proveedor de `.env` (llamada real). Por cada caso guarda:
   - `caso_NN.json`: el `Resultado` completo (propuesta entera, métricas, `trace_id`, `version_prompt`).
   - `caso_NN.txt`: la salida de terminal **completa y sin recortar**, exactamente como la imprime `python -m src.motor`.
3. Corre los casos de error y guarda su salida completa:
   - `error_reintento.txt`: simulador `invalido` (campo que falló, reintento, error estructurado).
   - `error_api.txt`: llamada real con una clave inválida a propósito (401).
   - `error_entrada.txt`: `consultas/extra/entrada_invalida.json`.
4. Escribe `medicion.md` y `medicion.json`, construidos **leyendo los `caso_NN.json` de esa misma carpeta**, nunca con otra llamada.
5. Escribe `manifiesto.json`: fecha, modelo, `version_prompt`, commit de git (`git rev-parse --short HEAD`), cantidad de casos y la lista de archivos con su hash SHA-256. Es el registro que demuestra que todo salió de la misma corrida.

Reglas:

- La ejecución exitosa que muestre el PDF es `caso_01.txt` de la corrida. Así la ficha y la fila 1 de la tabla son el mismo dato.
- `scripts.medir` y `scripts.evidencia` se pueden dejar como atajos que llaman a `scripts.corrida`, o borrar. No puede quedar ningún camino que haga una segunda llamada real para el mismo caso.
- Las corridas viejas (`resultados/medicion_20261030_1626.*` y `evidencia_*.txt`) se mueven a `resultados/historico/` con una nota de que son las que se entregaron en la PE2. No se borran.
- Prueba nueva en `tests/`, con el simulador: la corrida genera todos los archivos, `medicion.json` coincide con los `caso_NN.json` y el manifiesto lista los hashes correctos.

## Tarea 3. Reproducible desde un clon limpio

1. **Integración continua en GitHub Actions** (`.github/workflows/pruebas.yml`): en cada push y pull request, un checkout limpio en Ubuntu con Python 3.11 y 3.12 corre `pip install -r requirements.txt` y `python -m pytest -q`, **sin clave** (las pruebas no la necesitan). Agregar el badge de estado al principio del `README.md`. Es la evidencia permanente de que el repo se reproduce sin archivos no documentados.
2. **Prueba manual una vez**, en una carpeta nueva fuera del repo de trabajo: `git clone`, crear el entorno, instalar, copiar `.env.example` a `.env`, completar la clave y correr `python -m scripts.corrida`. Anotar en `docs/ESTADO.md` cualquier paso que el README no explicaba y corregir el README.
3. Revisar que `requirements.txt` fije versiones con rango (`>=x,<y`) para todo lo que se usa, y que `.env.example` liste todas las variables que lee el código y ninguna más.

## Tarea 4. Diez casos nuevos, ya clasificados por QA

Federico clasificó los 10 casos el 2026-11-02. El criterio es suyo y **no se modifica**; la redacción de las justificaciones se ajustó a una estructura fija (qué toca, por qué ese nivel, qué lo separa del nivel vecino) y la justificación queda en el campo `justificacion_qa`, que va a usar el juez LLM de la PE6.

| Caso | Qué cambia | Impacto esperado | Revalidación | Justificación de QA |
| --- | --- | --- | --- | --- |
| 06 | Parche del LIMS validado por el proveedor | menor | No | Parche correctivo sin cambios en flujos, cálculos ni base de datos: no toca la integridad de datos ni las decisiones del sistema. El riesgo está cubierto por el paquete de validación del proveedor, que QA revisa y acepta (GAMP 5, aprovechamiento de la documentación del proveedor). Es menor y no mayor porque no altera ninguna función GxP validada. |
| 07 | Nueva firma electrónica en la liberación de lotes | critico | Sí | Cambia el mecanismo de firma electrónica de la decisión de liberación, la última barrera de contención antes de que el producto llegue al mercado (21 CFR Part 11, Anexo 11). Es crítico y no mayor porque afecta directamente la atribución y validez de la decisión que libera el lote, sin importar si el método nuevo es más robusto. |
| 08 | Desactivar el audit trail del cromatográfico | critico | Sí | Desactivar el audit trail elimina la trazabilidad y la atribución de los datos de estabilidad (ALCOA+), y esos datos respaldan decisiones de liberación y de vida útil. Es crítico porque compromete la integridad de registros GxP de forma directa. QA no aprobaría el cambio: el pedido debe rechazarse o replantearse sin desactivar el audit trail. |
| 09 | Perfil de solo consulta en el LIMS | menor | No | Agrega un perfil de solo consulta: no permite cargar, modificar ni aprobar resultados, así que no afecta la calidad del producto ni las decisiones del sistema. Es menor porque solo cambia la matriz de accesos, que se documenta y se revisa en la revisión periódica de usuarios. |
| 10 | Reemplazo de balanza analítica que falló | mayor | Sí | El reemplazo se origina en una falla de verificación: además de calificar el equipo nuevo, hay que evaluar el impacto de la falla sobre los resultados obtenidos con la balanza retirada desde la última verificación conforme. Es mayor y no menor porque, aunque el modelo sea idéntico, se trata de un equipo nuevo que requiere calificación y la falla puede tener consecuencias sobre datos ya emitidos. |
| 11 | Traslado de la cámara de estabilidad | mayor | Sí | El traslado cambia las condiciones ambientales de una cámara con estudios en curso de productos comerciales: requiere recalificar la cámara (mapeo térmico y de humedad) y controlar que no haya excursiones durante el traslado. Es mayor y no crítico porque el riesgo afecta la validez de los datos de estabilidad, no al producto liberado ni directamente al paciente. |
| 12 | Errores de tipeo en un instructivo de limpieza | menor | No | Corrección de tipeo sin cambios en pasos, productos, concentraciones ni tiempos: no altera el método ni el resultado de la limpieza. Es menor porque es una revisión documental que se gestiona por el circuito de control de documentos. |
| 13 | Comprimidora fuera del rango validado | critico | Sí | Lleva el proceso fuera del rango validado (30 a 45 rpm) en un producto comercial, sin evidencia de que la calidad se mantenga a 55 rpm. Es crítico porque puede afectar atributos críticos del producto que llegan al paciente; solo podría implementarse después de validar el nuevo rango. |
| 14 | Redondeo de la valoración en el certificado | mayor | Sí | Cambia cómo el certificado de análisis informa un resultado que respalda la liberación, en un LIMS validado: según la cantidad de decimales de la especificación, el redondeo puede cambiar el veredicto en el límite. Es mayor y no menor por criterio conservador de QA: aunque alinea un criterio ya existente y no cambia el cálculo ni la especificación, requiere una verificación documentada de la nueva configuración y de los resultados en el límite de especificación. |
| 15 | Antivirus en PCs administrativas sin sistemas GxP | sin impacto | No | Equipos sin sistemas GxP y sin acceso a sistemas productivos: el cambio no alcanza procesos GxP, la calidad del producto ni al paciente. Es sin impacto porque queda fuera del alcance del sistema de calidad; se gestiona por el circuito de IT. |

Distribución: 3 menor, 3 mayor, 3 crítico, 1 sin impacto. Los casos 07, 08, 10, 11 y 13 están en la frontera mayor/crítico y el 14 en la frontera menor/mayor; 06, 09, 12 y 15 son anclas.

Crear cada archivo con este contenido exacto. El nombre puede llevar un sufijo descriptivo después del número, por ejemplo `07_firma_liberacion.json`:

**`consultas/06.json`**

```json
{
  "nombre": "Parche del LIMS validado por el proveedor",
  "tipo_prueba": "ancla",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "menor",
    "requiere_revalidacion": false,
    "justificacion_qa": "Parche correctivo sin cambios en flujos, cálculos ni base de datos: no toca la integridad de datos ni las decisiones del sistema. El riesgo está cubierto por el paquete de validación del proveedor, que QA revisa y acepta (GAMP 5, aprovechamiento de la documentación del proveedor). Es menor y no mayor porque no altera ninguna función GxP validada.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02"
  },
  "entrada": {
    "id_ccam": "CCAM-2026-106",
    "tipo_cambio": "version_software",
    "area_solicitante": "control_calidad",
    "sistema_afectado": "LIMS",
    "descripcion": "Actualizar el LIMS del parche 8.2.1 al 8.2.3. Corrige dos errores en la impresión de reportes. El proveedor entrega el paquete de validación del parche y declara que no cambian los flujos, la base de datos ni los cálculos."
  }
}
```
**`consultas/07.json`**

```json
{
  "nombre": "Nueva firma electrónica en la liberación de lotes",
  "tipo_prueba": "frontera",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "critico",
    "requiere_revalidacion": true,
    "justificacion_qa": "Cambia el mecanismo de firma electrónica de la decisión de liberación, la última barrera de contención antes de que el producto llegue al mercado (21 CFR Part 11, Anexo 11). Es crítico y no mayor porque afecta directamente la atribución y validez de la decisión que libera el lote, sin importar si el método nuevo es más robusto.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02"
  },
  "entrada": {
    "id_ccam": "CCAM-2026-107",
    "tipo_cambio": "version_software",
    "area_solicitante": "garantia_calidad",
    "sistema_afectado": "Sistema de liberación de lotes",
    "descripcion": "Migrar el sistema de liberación de lotes a la versión 5.0, que reemplaza el módulo de firma electrónica: el Director Técnico pasa a firmar con usuario y token en lugar de usuario y contraseña."
  }
}
```
**`consultas/08.json`**

```json
{
  "nombre": "Desactivar el audit trail del cromatográfico",
  "tipo_prueba": "frontera",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "critico",
    "requiere_revalidacion": true,
    "justificacion_qa": "Desactivar el audit trail elimina la trazabilidad y la atribución de los datos de estabilidad (ALCOA+), y esos datos respaldan decisiones de liberación y de vida útil. Es crítico porque compromete la integridad de registros GxP de forma directa. QA no aprobaría el cambio: el pedido debe rechazarse o replantearse sin desactivar el audit trail.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02",
    "nota": "QA rechazaría el cambio: el contrato actual no tiene un campo para expresarlo (ver observación O-1)."
  },
  "entrada": {
    "id_ccam": "CCAM-2026-108",
    "tipo_cambio": "configuracion_sistema",
    "area_solicitante": "control_calidad",
    "sistema_afectado": "Software cromatográfico",
    "descripcion": "Desactivar el audit trail del software cromatográfico durante dos semanas porque ralentiza el procesamiento de las corridas de estabilidad. Se reactivaría al terminar la campaña."
  }
}
```
**`consultas/09.json`**

```json
{
  "nombre": "Perfil de solo consulta en el LIMS",
  "tipo_prueba": "ancla",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "menor",
    "requiere_revalidacion": false,
    "justificacion_qa": "Agrega un perfil de solo consulta: no permite cargar, modificar ni aprobar resultados, así que no afecta la calidad del producto ni las decisiones del sistema. Es menor porque solo cambia la matriz de accesos, que se documenta y se revisa en la revisión periódica de usuarios.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02"
  },
  "entrada": {
    "id_ccam": "CCAM-2026-109",
    "tipo_cambio": "configuracion_sistema",
    "area_solicitante": "sistemas",
    "sistema_afectado": "LIMS",
    "descripcion": "Crear un perfil nuevo \"Analista en formación\" en el LIMS, con permisos solo de consulta: sin carga ni aprobación de resultados."
  }
}
```
**`consultas/10.json`**

```json
{
  "nombre": "Reemplazo de balanza analítica que falló",
  "tipo_prueba": "frontera",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "mayor",
    "requiere_revalidacion": true,
    "justificacion_qa": "El reemplazo se origina en una falla de verificación: además de calificar el equipo nuevo, hay que evaluar el impacto de la falla sobre los resultados obtenidos con la balanza retirada desde la última verificación conforme. Es mayor y no menor porque, aunque el modelo sea idéntico, se trata de un equipo nuevo que requiere calificación y la falla puede tener consecuencias sobre datos ya emitidos.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02"
  },
  "entrada": {
    "id_ccam": "CCAM-2026-110",
    "tipo_cambio": "equipo_instalacion",
    "area_solicitante": "control_calidad",
    "sistema_afectado": "Balanza analítica",
    "descripcion": "Reemplazar una balanza analítica por otra del mismo fabricante y modelo, porque la actual falló la verificación diaria. La nueva viene con certificado de calibración del proveedor."
  }
}
```
**`consultas/11.json`**

```json
{
  "nombre": "Traslado de la cámara de estabilidad",
  "tipo_prueba": "frontera",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "mayor",
    "requiere_revalidacion": true,
    "justificacion_qa": "El traslado cambia las condiciones ambientales de una cámara con estudios en curso de productos comerciales: requiere recalificar la cámara (mapeo térmico y de humedad) y controlar que no haya excursiones durante el traslado. Es mayor y no crítico porque el riesgo afecta la validez de los datos de estabilidad, no al producto liberado ni directamente al paciente.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02"
  },
  "entrada": {
    "id_ccam": "CCAM-2026-111",
    "tipo_cambio": "equipo_instalacion",
    "area_solicitante": "control_calidad",
    "sistema_afectado": "Cámara de estabilidad 25 °C / 60 % HR",
    "descripcion": "Trasladar la cámara de estabilidad de 25 °C / 60 % HR a otra sala, con otro sistema de climatización, por una obra en el sector. Tiene estudios en curso de tres productos comerciales."
  }
}
```
**`consultas/12.json`**

```json
{
  "nombre": "Errores de tipeo en un instructivo de limpieza",
  "tipo_prueba": "ancla",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "menor",
    "requiere_revalidacion": false,
    "justificacion_qa": "Corrección de tipeo sin cambios en pasos, productos, concentraciones ni tiempos: no altera el método ni el resultado de la limpieza. Es menor porque es una revisión documental que se gestiona por el circuito de control de documentos.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02"
  },
  "entrada": {
    "id_ccam": "CCAM-2026-112",
    "tipo_cambio": "documento_procedimiento",
    "area_solicitante": "produccion",
    "sistema_afectado": "Instructivo de limpieza de la línea 3",
    "descripcion": "Corregir errores de tipeo en el instructivo de limpieza de la línea 3 (\"detergnete\", \"enjaguar\"), sin cambiar pasos, productos, concentraciones ni tiempos."
  }
}
```
**`consultas/13.json`**

```json
{
  "nombre": "Comprimidora fuera del rango validado",
  "tipo_prueba": "frontera",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "critico",
    "requiere_revalidacion": true,
    "justificacion_qa": "Lleva el proceso fuera del rango validado (30 a 45 rpm) en un producto comercial, sin evidencia de que la calidad se mantenga a 55 rpm. Es crítico porque puede afectar atributos críticos del producto que llegan al paciente; solo podría implementarse después de validar el nuevo rango.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02"
  },
  "entrada": {
    "id_ccam": "CCAM-2026-113",
    "tipo_cambio": "proceso_productivo",
    "area_solicitante": "produccion",
    "sistema_afectado": "Comprimidora rotativa de la línea 2",
    "descripcion": "Aumentar la velocidad de la comprimidora de 40 a 55 rpm en un producto comercial para recuperar atrasos de producción. El rango validado del proceso es de 30 a 45 rpm."
  }
}
```
**`consultas/14.json`**

```json
{
  "nombre": "Redondeo de la valoración en el certificado",
  "tipo_prueba": "frontera",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "mayor",
    "requiere_revalidacion": true,
    "justificacion_qa": "Cambia cómo el certificado de análisis informa un resultado que respalda la liberación, en un LIMS validado: según la cantidad de decimales de la especificación, el redondeo puede cambiar el veredicto en el límite. Es mayor y no menor por criterio conservador de QA: aunque alinea un criterio ya existente y no cambia el cálculo ni la especificación, requiere una verificación documentada de la nueva configuración y de los resultados en el límite de especificación.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02",
    "nota": "Caso de frontera menor/mayor. QA lo considera menor en lo técnico, pero lo eleva a mayor ante la duda (ver regla R-QA-01). Si el modelo propone menor con verificación, registrarlo como discrepancia de frontera, no como error grave."
  },
  "entrada": {
    "id_ccam": "CCAM-2026-114",
    "tipo_cambio": "configuracion_sistema",
    "area_solicitante": "control_calidad",
    "sistema_afectado": "LIMS",
    "descripcion": "Cambiar el redondeo de la valoración en el certificado de análisis de dos decimales a uno, para unificar el formato con el de la casa matriz. El cálculo interno y la especificación no cambian."
  }
}
```
**`consultas/15.json`**

```json
{
  "nombre": "Antivirus en PCs administrativas sin sistemas GxP",
  "tipo_prueba": "ancla",
  "esperado": {
    "fuera_de_alcance": false,
    "impacto_gxp": "sin_impacto",
    "requiere_revalidacion": false,
    "justificacion_qa": "Equipos sin sistemas GxP y sin acceso a sistemas productivos: el cambio no alcanza procesos GxP, la calidad del producto ni al paciente. Es sin impacto porque queda fuera del alcance del sistema de calidad; se gestiona por el circuito de IT.",
    "clasificado_por": "Federico Bongiovanni (QA/CSV)",
    "fecha": "2026-11-02"
  },
  "entrada": {
    "id_ccam": "CCAM-2026-115",
    "tipo_cambio": "otro",
    "area_solicitante": "sistemas",
    "sistema_afectado": "PCs del área administrativa",
    "descripcion": "Actualizar el antivirus y el navegador en las computadoras de Recursos Humanos y Compras. No tienen instalado ningún sistema GxP ni acceden a sistemas productivos."
  }
}
```

`scripts.corrida` toma todos los `consultas/0*.json` y `consultas/1*.json`: quince casos en total. La coincidencia se informa también separada por grupo (los 5 originales, las anclas y la frontera) y por nivel, para ver si el modelo sobreclasifica siempre para el mismo lado.

### Regla de QA R-QA-01: ante la duda real, el nivel más alto

Acordada con Federico el 2026-11-02 al cerrar el caso 14: cuando un cambio queda entre dos niveles **porque falta un dato o el riesgo es incierto**, se clasifica en el nivel más alto y se pide el dato. No es licencia para subir el nivel cuando el dato está: en el CCAM 01 el modelo propuso crítico con la información suficiente para decir mayor, y eso sigue siendo una sobreclasificación (hallazgo H-01).

Agregarla a `prompts/sistema.md` recién en la PE3, junto con los SOPs, para que la medición de esta corrida siga comparable con la de la PE2. Registrarla en `docs/DECISIONES.md` como D-17.

### Observación O-1 (no implementar todavía)

En el caso 08, QA no solo clasifica: **rechaza** el cambio. El contrato actual no tiene cómo expresar «este cambio no debería aprobarse». Federico decide si en la PE3 se suma a `Salida` un campo cerrado, por ejemplo `recomendacion: proceder | proceder_con_condiciones | no_proceder`. Hasta que lo decida, el caso se evalúa solo por impacto y revalidación, y en `docs/ESTADO.md` queda anotado como decisión pendiente.

## Al terminar

- `README.md`: badge de CI, comando `scripts.corrida`, sección "Reproducir desde un clon limpio".
- `docs/DECISIONES.md`:
  - D-14: una sola corrida como fuente de verdad, con manifiesto y hashes.
  - D-15: integración continua sin clave como prueba de reproducibilidad.
  - D-16: los tags no se mueven; las correcciones van en `pe2.1` o en la PE siguiente.
  - D-17: regla R-QA-01, ante la duda real el nivel más alto (se incorpora al prompt en la PE3).
- `docs/ESTADO.md`: actualizar la tabla y la bitácora, y anotar la decisión pendiente O-1.
- `docs/TRASPASO_PE2_CORRECCIONES.md` para la app: la carpeta de la corrida nueva y el resultado de la prueba desde un clon limpio. La app regenera el PDF desde esa carpeta.

## Criterios de aceptación

- [ ] `git ls-remote --tags origin` muestra `refs/tags/pe2` apuntando a `c92b40d`.
- [ ] `python -m scripts.corrida` genera la carpeta con los 5 `caso_NN`, los 3 `error_*`, `medicion.*` y `manifiesto.json`.
- [ ] La fila 1 de `medicion.json` y `caso_01.json` tienen los mismos tokens, costo, latencia y `trace_id`.
- [ ] Ningún `.txt` de la corrida tiene texto recortado.
- [ ] GitHub Actions en verde en un checkout limpio, sin clave.
- [ ] La prueba manual desde un clon nuevo funciona siguiendo solo el README.
- [ ] Están los 10 casos nuevos con el `esperado` y la `justificacion_qa` exactos de este pedido.
- [ ] La medición informa la coincidencia total, por grupo y por nivel de impacto.
- [ ] `python -m pytest -q` en verde, con las pruebas nuevas.
