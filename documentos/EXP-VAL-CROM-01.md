---
codigo: EXP-VAL-CROM-01
titulo: Expediente de validación del software cromatográfico de Control de Calidad
version: 2
vigente_desde: 2026-03-30
roles_lectura: validaciones, jefe_qa
---

# EXP-VAL-CROM-01 Expediente de validación del software cromatográfico de Control de Calidad

> Documento ficticio, creado para el proyecto académico. No corresponde a ninguna empresa real. Código de control del documento: TESTIGO-VAL-4408.

## 1 Sistema

Software cromatográfico de Control de Calidad, categoría GAMP 4, versión 7.2, conectado a los equipos HPLC-QC-01 a HPLC-QC-04. Los resultados de valoración se transfieren al LIMS por interfaz validada.

## 2 Estrategia de validación

Validación basada en riesgo. Se aprovecharon las pruebas de fábrica del proveedor para las funciones estándar; se probaron con protocolo propio las funciones configuradas: cálculos de valoración, integración, audit trail, firmas y transferencia al LIMS.

## 3 Resultados por equipo

### 3.1 HPLC-QC-01

OQ del software ejecutado sin desviaciones. Conexión al LIMS verificada con 20 transferencias.

### 3.2 HPLC-QC-02

OQ ejecutado con una desviación menor (DEV-VAL-2026-07, etiqueta de reporte) cerrada antes de la aprobación.

### 3.3 HPLC-QC-03

OQ del software ejecutado sin desviaciones. Verificación de cálculos de valoración y uniformidad de contenido con 12 casos, incluidos 4 en el límite de especificación. Liberado para uso en producto terminado.

### 3.4 HPLC-QC-04

OQ del software ejecutado sin desviaciones. Verificación de cálculos de sustancias relacionadas con 12 casos, incluidos 4 en el límite de reporte. Liberado para uso en estudios de estabilidad.

## 4 Funciones críticas

Cálculo de valoración, cálculo de impurezas, audit trail, firma electrónica de aprobación de resultados y transferencia al LIMS. Un cambio en cualquiera de estas funciones requiere revalidación de la función afectada según SOP-VS-002.

## 5 Conclusión

El sistema está validado para su uso previsto desde el 30 de marzo de 2026. Próxima revisión periódica: marzo de 2028.
