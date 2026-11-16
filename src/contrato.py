"""Contrato de datos del motor (HU-01 de la PE1).

Criterio de diseño: texto libre solo para lo que lee una persona
(justificación, descripción de tareas). Todo lo que dispara una decisión
o se registra en el sistema va cerrado: Enum, rango, patrón o valor fijo.
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

import re

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

RAIZ = Path(__file__).resolve().parent.parent
CATALOGO_SOPS: dict[str, str] = {
    s["codigo"]: s["titulo"]
    for s in json.loads((RAIZ / "config" / "catalogo_sops.json").read_text(encoding="utf-8"))["sops"]
}


class TipoCambio(str, Enum):
    version_software = "version_software"
    configuracion_sistema = "configuracion_sistema"
    packaging_rotulado = "packaging_rotulado"
    proveedor_material = "proveedor_material"
    equipo_instalacion = "equipo_instalacion"
    documento_procedimiento = "documento_procedimiento"
    proceso_productivo = "proceso_productivo"
    otro = "otro"


class Area(str, Enum):
    produccion = "produccion"
    control_calidad = "control_calidad"
    garantia_calidad = "garantia_calidad"
    validaciones = "validaciones"
    sistemas = "sistemas"
    mantenimiento = "mantenimiento"
    deposito = "deposito"
    compras = "compras"
    asuntos_regulatorios = "asuntos_regulatorios"


class ImpactoGxP(str, Enum):
    sin_impacto = "sin_impacto"
    menor = "menor"
    mayor = "mayor"
    critico = "critico"


# ---------------------------------------------------------------- Entrada
class Entrada(BaseModel):
    """Lo que carga el solicitante en el paso 1 del AS-IS."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id_ccam: str = Field(..., pattern=r"^CCAM-\d{4}-\d{3,4}$",
                         description="Identificador ficticio, formato CCAM-AAAA-NNN")
    tipo_cambio: TipoCambio
    area_solicitante: Area
    sistema_afectado: str = Field(..., min_length=3, max_length=120,
                                  description="Sistema, equipo, producto o documento alcanzado")
    descripcion: str = Field(..., min_length=30, max_length=2000,
                             description="Qué se cambia y por qué; mínimo 30 caracteres")


# ---------------------------------------------------------------- Salida
# Código de documento controlado: SOP-VS-002, INF-AUD-2026-03, EXP-VAL-CROM-01, HAL-INSP-2026-01...
PATRON_CODIGO = r"[A-Z]{3}-[A-Z0-9]{2,5}(?:-[A-Z0-9]{2,5}){1,3}"


def seccion_cubierta(seccion: str, recuperadas: set[str] | list[str]) -> bool:
    """¿La sección citada está entre las recuperadas? Vale la misma, una subsección o la sección madre."""
    return any(seccion == r or seccion.startswith(r + ".") or r.startswith(seccion + ".") for r in recuperadas)


class ReferenciaSOP(BaseModel):
    """Una cita: documento y sección.

    Sin contexto (motor de la PE2): el código tiene que estar en el catálogo cerrado.
    Con contexto {"fuentes": {codigo: {secciones}}} (RAG de la PE3): tiene que estar
    entre los fragmentos recuperados EN ESTA llamada. Una cita que no se recuperó es inventada.
    """
    model_config = ConfigDict(extra="forbid")

    codigo: str = Field(..., pattern=rf"^{PATRON_CODIGO}$")
    seccion: str = Field(..., pattern=r"^\d+(\.\d+)*$", description="Ej.: 5.2")

    @field_validator("codigo")
    @classmethod
    def codigo_valido(cls, v: str, info: ValidationInfo) -> str:
        fuentes = (info.context or {}).get("fuentes")
        if fuentes is None:
            if v not in CATALOGO_SOPS:
                raise ValueError(f"{v} no existe en el catálogo de procedimientos vigente")
        elif v not in fuentes:
            raise ValueError(f"{v} no está entre las fuentes recuperadas en esta consulta (cita no respaldada)")
        return v

    @model_validator(mode="after")
    def seccion_recuperada(self, info: ValidationInfo) -> "ReferenciaSOP":
        fuentes = (info.context or {}).get("fuentes")
        if fuentes is not None and self.codigo in fuentes and not seccion_cubierta(self.seccion, fuentes[self.codigo]):
            raise ValueError(f"{self.codigo} §{self.seccion} no está entre las secciones recuperadas "
                             f"({', '.join(sorted(fuentes[self.codigo]))})")
        return self


class Tarea(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descripcion: str = Field(..., min_length=15, max_length=300)
    area_responsable: Area


class Salida(BaseModel):
    """Propuesta de evaluación de impacto. Siempre es un borrador para QA."""

    model_config = ConfigDict(extra="forbid")

    fuera_de_alcance: bool = Field(
        ..., description="true si la consulta no es un cambio GxP evaluable; se deriva a QA sin clasificar")
    requiere_humano: bool = Field(
        False, description="true si la evidencia recuperada no alcanza para clasificar: no se clasifica y se deriva a QA (PE3)")
    impacto_gxp: Optional[ImpactoGxP] = Field(
        ..., description="null solo si fuera_de_alcance es true")
    requiere_revalidacion: bool
    justificacion: str = Field(..., min_length=40, max_length=1200)
    fundamento: list[ReferenciaSOP] = Field(default_factory=list, max_length=6)
    tareas: list[Tarea] = Field(default_factory=list, max_length=10)
    confianza: float = Field(..., ge=0.0, le=1.0)
    estado: Literal["BORRADOR_PENDIENTE_QA"] = "BORRADOR_PENDIENTE_QA"

    @model_validator(mode="after")
    def reglas_cruzadas(self) -> "Salida":
        # H-02 (devolución PE2): todo código que se nombra en una tarea tiene que estar en el fundamento
        citados = {f.codigo for f in self.fundamento}
        for i, t in enumerate(self.tareas):
            sueltos = set(re.findall(rf"\b{PATRON_CODIGO}\b", t.descripcion)) - citados
            if sueltos:
                raise ValueError(f"la tarea {i} nombra {', '.join(sorted(sueltos))}, que no figura en fundamento (H-02)")
        if self.fuera_de_alcance:
            if self.requiere_humano or self.impacto_gxp is not None or self.tareas or self.requiere_revalidacion:
                raise ValueError("fuera_de_alcance=true exige impacto_gxp=null, sin tareas, sin revalidación "
                                 "y requiere_humano=false")
            return self
        if self.requiere_humano:
            if self.impacto_gxp is not None or self.tareas or self.requiere_revalidacion:
                raise ValueError("requiere_humano=true exige impacto_gxp=null, sin tareas y sin revalidación: "
                                 "sin evidencia no se clasifica")
            return self
        if self.impacto_gxp is None:
            raise ValueError("impacto_gxp es obligatorio cuando la consulta está dentro de alcance")
        if not self.fundamento:
            raise ValueError("toda propuesta dentro de alcance debe citar al menos un SOP (HU-01, criterio 1)")
        if self.impacto_gxp in (ImpactoGxP.mayor, ImpactoGxP.critico) and not self.tareas:
            raise ValueError("impacto mayor o crítico exige al menos una tarea")
        if self.requiere_revalidacion and self.impacto_gxp == ImpactoGxP.sin_impacto:
            raise ValueError("requiere_revalidacion=true es incompatible con impacto sin_impacto")
        return self


class ErrorEstructurado(BaseModel):
    """Lo único que ve el cliente cuando el motor no puede dar una propuesta válida."""

    error: Literal["entrada_invalida", "salida_invalida", "acceso_denegado", "sin_base_documental", "api_limite_uso", "api_sin_conexion",
                   "api_autenticacion", "api_error", "configuracion"]
    mensaje: str
    campos: list[dict] = Field(default_factory=list, description="[{campo, problema}] tomados de ValidationError")
    intentos: int = 0
    accion: str = "Derivar a QA para evaluación manual"
