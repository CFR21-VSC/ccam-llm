"""Servidor MCP propio: la "puerta" del sistema de gestión de cambios (PE4).

QUÉ HACE ESTE ARCHIVO
    Expone el sistema del cliente con tres herramientas tipadas:
        consultar_ccam        lectura: los datos y el estado de un CCAM
        listar_ccam           lectura: los CCAM en un estado
        registrar_evaluacion  ESCRITURA: guarda el borrador de evaluación
    El agente (o cualquier cliente MCP) pregunta qué herramientas hay
    (list_tools), lee sus descripciones y parámetros, y pide una (call_tool).
    Corre como un programa aparte y habla por entrada/salida estándar (stdio).

    python -m src.mcp_servidor          # lo arranca el cliente; no hace falta a mano

EQUIVALENTE GxP
    La interfaz validada de un sistema: qué operaciones se pueden hacer, con
    qué datos y nada más. Los controles de segregación (quien pide no aprueba,
    aprueba solo QA formal) se repiten acá, del lado del sistema: si el agente
    fallara, el sistema igual rechaza.

CONTRATO PARA LA PE5
    Los nombres, parámetros y respuestas de estas herramientas no cambian
    cuando detrás haya un sistema legacy: solo cambia src/sistema.py.
"""
from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from src import sistema

servidor = MCPServer(
    "sistema-ccam", log_level="WARNING",
    instructions="Sistema de gestión de cambios GxP (simulado). Lectura libre según rol; "
                 "la escritura registra borradores y exige aprobación de QA formal.")

IdCCAM = Annotated[str, Field(pattern=r"^CCAM-\d{4}-\d{3,4}$",
                              description="Número del pedido de cambio, por ejemplo CCAM-2026-108")]
Estado = Literal["abierto", "en_evaluacion", "borrador_registrado", "vencido", "cerrado"]
Impacto = Literal["sin_impacto", "menor", "mayor", "critico"]
Cita = Annotated[str, Field(pattern=r"^[A-Z]{3}-[A-Z0-9]{2,5}(-[A-Z0-9]{2,5}){1,3} §\d+(\.\d+)*$",
                            description="Documento y sección, por ejemplo 'SOP-VS-002 §6.3'")]
Usuario = Annotated[str, Field(pattern=r"^u_[a-z_]+$", description="Usuario del sistema, por ejemplo u_analista_qa")]


@servidor.tool()
def consultar_ccam(id_ccam: IdCCAM) -> dict:
    """Devuelve los datos de UN pedido de cambio (CCAM): tipo, área, sistema afectado, descripción,
    estado (abierto, en_evaluacion, borrador_registrado, vencido, cerrado), fecha límite y los borradores
    de evaluación ya registrados. Solo lectura: no modifica nada. Usala cuando la persona pregunta por
    un CCAM puntual o antes de evaluarlo."""
    try:
        return sistema.consultar(id_ccam)
    except sistema.ErrorSistema as exc:
        raise ToolError(str(exc)) from None


@servidor.tool()
def listar_ccam(estado: Estado) -> list[dict]:
    """Lista los pedidos de cambio que están en un estado (por ejemplo, todos los abiertos o todos los
    vencidos), con número, tipo, sistema afectado y fecha límite. Solo lectura. Usala cuando la persona
    pregunta por varios CCAM a la vez."""
    try:
        return sistema.listar(estado)
    except sistema.ErrorSistema as exc:
        raise ToolError(str(exc)) from None


@servidor.tool()
def registrar_evaluacion(
    id_ccam: IdCCAM,
    impacto: Impacto,
    requiere_revalidacion: bool,
    fundamento: Annotated[list[Cita], Field(min_length=1, max_length=8)],
    justificacion: Annotated[str, Field(min_length=20, max_length=1200)],
    solicitado_por: Usuario,
    aprobado_por: Usuario,
) -> dict:
    """ESCRITURA. Registra en el sistema el borrador de evaluación de impacto de un CCAM (queda como
    BORRADOR_PENDIENTE_QA; no aprueba el cambio). Requiere aprobación humana previa: aprobado_por tiene
    que ser QA formal (rol jefe_qa) y distinto de solicitado_por. Cambia el estado del CCAM a
    borrador_registrado y deja una fila en la auditoría."""
    try:
        return sistema.registrar_evaluacion(id_ccam, impacto, requiere_revalidacion, list(fundamento),
                                            justificacion, solicitado_por, aprobado_por)
    except sistema.ErrorSistema as exc:
        raise ToolError(str(exc)) from None


if __name__ == "__main__":
    servidor.run()
