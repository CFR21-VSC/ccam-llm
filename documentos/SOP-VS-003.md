---
codigo: SOP-VS-003
titulo: Evaluación de riesgo e integridad de datos
version: 2
vigente_desde: 2026-01-10
roles_lectura: solicitante, analista_qa, validaciones, jefe_qa
---

# SOP-VS-003 Evaluación de riesgo e integridad de datos

> Documento ficticio, creado para el proyecto académico. No corresponde a ninguna empresa real.

## 1 Objetivo

Asegurar que los datos GxP cumplan los principios ALCOA+ (atribuibles, legibles, contemporáneos, originales, exactos, completos, consistentes, perdurables y disponibles) y que los riesgos sobre esos datos se evalúen antes de cualquier cambio.

## 2 Alcance

Registros electrónicos y firmas electrónicas de sistemas GxP, según 21 CFR Part 11 y el Anexo 11 de las GMP.

## 3 Audit trail

### 3.1 Requisito

Todo sistema que crea, modifica o elimina registros GxP mantiene un audit trail activo, que registra quién, cuándo, qué cambió y por qué.

### 3.2 Prohibición de desactivarlo

El audit trail de un sistema GxP **no se desactiva** por razones de rendimiento, capacidad o comodidad operativa. Un pedido de cambio que proponga desactivarlo, aun en forma temporal, no se implementa; el problema de rendimiento se resuelve por otra vía (infraestructura, archivado).

### 3.3 Revisión

El audit trail se revisa como parte de la revisión de datos antes de aprobar resultados.

## 4 Firmas electrónicas

Las firmas electrónicas son únicas, están vinculadas a su registro e indican significado (revisión, aprobación, liberación). Cambiar el mecanismo de firma de una decisión de liberación cambia la atribución de esa decisión: requiere revalidación del sistema y aprobación del Jefe de Garantía de Calidad.

## 5 Evaluación de riesgo

### 5.1 Método

El riesgo de un cambio sobre los datos se evalúa por severidad (efecto sobre el paciente, el producto o la decisión), probabilidad y detectabilidad.

### 5.2 Formato y redondeo de resultados

El valor informado de un resultado se redondea a la misma cantidad de decimales con que está expresada la especificación. Cambiar el redondeo o el formato de un resultado informado en un certificado de análisis puede cambiar el veredicto en el límite de especificación: requiere una verificación documentada de la configuración y de casos en el límite.

## 6 Control de accesos

Los perfiles de usuario siguen el principio de mínimo privilegio. Quien registra un resultado no lo aprueba. Los perfiles que solo permiten consulta no otorgan capacidad de crear, modificar ni aprobar registros.
