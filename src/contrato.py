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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
class ReferenciaSOP(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str = Field(..., pattern=r"^SOP-[A-Z]{2}-\d{3}$")
    seccion: str = Field(..., pattern=r"^\d+(\.\d+)*$", description="Ej.: 5.2")

    @field_validator("codigo")
    @classmethod
    def codigo_en_catalogo(cls, v: str) -> str:
        if v not in CATALOGO_SOPS:
            raise ValueError(f"{v} no existe en el catálogo de procedimientos vigente")
        return v


class Tarea(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descripcion: str = Field(..., min_length=15, max_length=300)
    area_responsable: Area


class Salida(BaseModel):
    """Propuesta de evaluación de impacto. Siempre es un borrador para QA."""

    model_config = ConfigDict(extra="forbid")

    fuera_de_alcance: bool = Field(
        ..., description="true si la consulta no es un cambio GxP evaluable; se deriva a QA sin clasificar")
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
        if self.fuera_de_alcance:
            if self.impacto_gxp is not None or self.tareas or self.requiere_revalidacion:
                raise ValueError("fuera_de_alcance=true exige impacto_gxp=null, sin tareas y sin revalidación")
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

    error: Literal["entrada_invalida", "salida_invalida", "api_limite_uso", "api_sin_conexion",
                   "api_autenticacion", "api_error", "configuracion"]
    mensaje: str
    campos: list[dict] = Field(default_factory=list, description="[{campo, problema}] tomados de ValidationError")
    intentos: int = 0
    accion: str = "Derivar a QA para evaluación manual"
