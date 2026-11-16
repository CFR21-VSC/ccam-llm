---
codigo: SOP-CC-001
titulo: Gestión de control de cambios
version: 3
vigente_desde: 2026-03-01
roles_lectura: solicitante, analista_qa, validaciones, jefe_qa
---

# SOP-CC-001 Gestión de control de cambios

> Documento ficticio, creado para el proyecto académico. No corresponde a ninguna empresa real.

## 1 Objetivo

Establecer cómo se solicita, evalúa, aprueba, implementa y cierra un cambio (CCAM) que pueda afectar productos, procesos, sistemas, equipos, materiales o documentos alcanzados por las Buenas Prácticas de Fabricación.

## 2 Alcance

Aplica a todo cambio planificado en áreas GxP: Producción, Control de Calidad, Garantía de Calidad, Validaciones, Mantenimiento, Depósito, Compras, Sistemas y Asuntos Regulatorios. No aplica a cambios en equipos o sistemas que no participan de procesos GxP; esos cambios se gestionan por los circuitos propios de cada área (por ejemplo, el de Tecnología para la informática administrativa).

## 3 Responsabilidades

- **Solicitante:** abre el CCAM, describe el cambio y su motivo.
- **Áreas involucradas:** proponen la evaluación de impacto y las tareas de su competencia.
- **Garantía de Calidad:** revisa la evaluación de impacto, define el nivel y aprueba o rechaza.
- **Jefe de Garantía de Calidad:** aprueba los cambios de impacto mayor y crítico y firma el cierre.
- Quien abre un CCAM no puede aprobarlo (segregación de funciones).

## 4 Etapas del CCAM

1. Inicio y justificación.
2. Definición de las personas involucradas.
3. Evaluación de impacto y tareas a realizar.
4. Registro de tareas cumplidas.
5. Resultado de la implementación.
6. Distribución.
7. Aprobación y cierre.

## 5 Matriz de clasificación del impacto GxP

### 5.1 Principio de clasificación

El nivel de impacto se define por el **efecto** que el cambio puede tener sobre cuatro objetos: la calidad del producto, la seguridad del paciente, la decisión de liberación de un lote y la integridad de los datos que respaldan esas decisiones.

Que un sistema esté validado o un equipo calificado **no eleva por sí solo el nivel**. Lo eleva que el cambio modifique una función, un cálculo, un dato, un flujo de decisión o un estado validado o calificado. Un cambio sobre un sistema validado que no altera ninguna de esas cosas puede ser menor.

### 5.2 Sin impacto

El cambio no alcanza ningún proceso, sistema, equipo, material ni documento GxP. Queda fuera del sistema de calidad y no requiere evaluación de impacto GxP.

Ejemplo ilustrativo: cambiar el mobiliario de la sala de reuniones de Compras.

### 5.3 Menor

El cambio toca un elemento GxP pero no modifica ninguna función, cálculo, dato, decisión ni estado validado, y su riesgo está controlado y documentado. No requiere revalidación ni recalificación; alcanza con una verificación documentada o con la documentación del proveedor revisada por Garantía de Calidad.

Ejemplos ilustrativos:

- Reemplazar el monitor de una estación de trabajo que ejecuta software validado.
- Agregar el logo actualizado de la empresa en el encabezado de un registro, sin cambiar campos.
- Ampliar la lista de distribución de un procedimiento vigente.

### 5.4 Mayor

El cambio modifica, o puede afectar, un estado validado o calificado, o los datos que respaldan una decisión de calidad, **pero existe una barrera posterior** (evaluación de riesgo, verificación, recalificación o revalidación antes de usar el resultado) que impide que el efecto llegue al producto liberado o al paciente. Requiere evaluación de riesgo y, en general, revalidación o recalificación parcial.

Ejemplos ilustrativos:

- Cambiar el proveedor del gas de arrastre de un cromatógrafo.
- Mover un lector de código de barras a otra línea de acondicionamiento.
- Incorporar un nuevo tipo de ensayo a un sistema de laboratorio, con su verificación previa.

### 5.5 Crítico

El cambio puede alterar **directamente y sin otra barrera** la calidad, seguridad o eficacia del producto que llega al paciente, la decisión que libera un lote, o la integridad de los registros que la respaldan. Requiere revalidación, puede requerir notificación regulatoria y, en algunos casos, no debe aprobarse.

Situaciones típicas de nivel crítico:

- Cambiar cómo se firma, registra o atribuye la decisión de liberación de un lote.
- Desactivar, reducir o eludir controles de integridad de datos de registros regulados (audit trail, firmas electrónicas, control de accesos de aprobación).
- Operar un proceso o equipo fuera del rango validado en producto comercial.
- Cambiar una especificación de liberación o el método que la verifica sin validación previa.

### 5.6 Frontera entre mayor y crítico

Ante la duda entre mayor y crítico, Garantía de Calidad se pregunta: **¿el cambio puede alterar, sin otra barrera, un resultado o una decisión que libera producto?** Si la respuesta es sí, es crítico. Si existe una barrera (por ejemplo, una recalificación antes de volver a usar el equipo, o datos que respaldan la vida útil pero no la liberación de un lote), es mayor.

### 5.7 Frontera entre menor y mayor

Ante la duda entre menor y mayor, la pregunta es: **¿el cambio modifica una función, un cálculo, un dato o un estado validado?** Si no lo modifica y el riesgo está documentado, es menor, aunque el sistema esté validado. Si lo modifica, es mayor.

### 5.8 Regla R-QA-01: ante la duda real

Cuando la información disponible no alcanza para decidir entre dos niveles, se clasifica en el nivel más alto y se pide el dato que falta. Esta regla aplica **solo** cuando falta información: si el dato está en la descripción del cambio, se clasifica por el efecto real, sin subir el nivel por precaución.

## 6 Evaluación de impacto

La evaluación de impacto de cada CCAM contiene: el nivel según la sección 5, si requiere revalidación o recalificación, la justificación con los procedimientos aplicables y las tareas con su área responsable. Toda evaluación es un borrador hasta que Garantía de Calidad la aprueba.

## 7 Plazos

- Evaluación de impacto: 10 días hábiles desde la apertura.
- Cierre de un CCAM de impacto menor: 40 días corridos.
- Los CCAM de impacto mayor y crítico se cierran según el plan de implementación aprobado.

## 8 Registros

El CCAM, su evaluación de impacto, las tareas cumplidas y la aprobación se registran en el sistema de gestión de cambios. El sistema conserva el audit trail de cada modificación.
