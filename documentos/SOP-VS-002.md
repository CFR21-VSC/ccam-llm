---
codigo: SOP-VS-002
titulo: Validación de sistemas computarizados
version: 4
vigente_desde: 2026-02-15
roles_lectura: solicitante, analista_qa, validaciones, jefe_qa
---

# SOP-VS-002 Validación de sistemas computarizados

> Documento ficticio, creado para el proyecto académico. No corresponde a ninguna empresa real.

## 1 Objetivo

Definir el ciclo de vida de validación de los sistemas computarizados GxP con un enfoque basado en riesgo, según GAMP 5 y el Anexo 11 de las GMP.

## 2 Alcance

Aplica a los sistemas computarizados que generan, procesan o almacenan datos GxP: LIMS, software cromatográfico, sistema de liberación de lotes, sistema de gestión de cambios y sistemas de monitoreo ambiental.

## 3 Categorías de software

- **Categoría 1:** infraestructura (sistemas operativos, bases de datos).
- **Categoría 3:** productos no configurados.
- **Categoría 4:** productos configurados (LIMS, software cromatográfico).
- **Categoría 5:** aplicaciones a medida.

## 4 Ciclo de vida

Concepto, proyecto (especificaciones, verificación), operación y retiro. La verificación se dimensiona por el riesgo de cada función sobre la seguridad del paciente, la calidad del producto y la integridad de datos.

## 5 Uso de la documentación del proveedor

Cuando el proveedor entrega evidencia de pruebas de una versión o parche (notas de versión, pruebas de fábrica, paquete de validación), Garantía de Calidad la revisa y decide si la acepta. Si el parche es correctivo y no cambia funciones, cálculos, flujos ni la estructura de datos, la evidencia del proveedor revisada puede reemplazar las pruebas propias; se documenta la revisión y no se requiere revalidación.

## 6 Cambios en sistemas validados

### 6.1 Evaluación

Todo cambio en un sistema validado se gestiona por SOP-CC-001. La evaluación identifica qué funciones cambian y su riesgo.

### 6.2 Cambios de configuración

Un cambio de configuración que altera una función, un cálculo, un formato de resultado informado o un flujo de aprobación requiere pruebas documentadas de la función afectada. Los cambios en perfiles de usuario que solo otorgan permisos de consulta se documentan en la matriz de accesos y se verifican en la revisión periódica de usuarios.

### 6.3 Revalidación por cambio de versión

Un cambio de versión mayor que modifica funciones, la base de datos o los cálculos requiere revalidación con pruebas de regresión de las funciones GxP. La profundidad depende del riesgo: si la versión afecta resultados que se usan para liberar producto, la revalidación se completa antes del uso productivo.

### 6.4 Migración de datos

Toda migración de datos GxP requiere un plan con respaldo previo, verificación de integridad de los registros migrados y conservación del audit trail histórico.

## 7 Retiro

Al retirar un sistema se asegura la disponibilidad y legibilidad de los datos GxP durante su período de retención.
