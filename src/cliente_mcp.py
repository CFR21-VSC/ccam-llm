"""Cliente MCP: cómo el agente (o un script) habla con el servidor del sistema.

Cada llamada arranca el servidor como un proceso aparte, conversa por stdio y lo cierra.
Es lo más simple y lo más aislado; para pocos pedidos por conversación alcanza.

EQUIVALENTE GxP
    El operador que usa la interfaz del sistema: pregunta qué operaciones hay y pide una.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RAIZ = Path(__file__).resolve().parent.parent


class ErrorMCP(Exception):
    """La herramienta respondió con error (por ejemplo, un CCAM que no existe o una aprobación inválida)."""


def _parametros() -> StdioServerParameters:
    entorno = {**os.environ, "PYTHONPATH": str(RAIZ), "PYTHONIOENCODING": "utf-8"}
    return StdioServerParameters(command=sys.executable, args=["-m", "src.mcp_servidor"], env=entorno, cwd=str(RAIZ))


async def _sesion(trabajo):
    async with stdio_client(_parametros()) as (lectura, escritura):
        async with ClientSession(lectura, escritura) as sesion:
            await sesion.initialize()
            return await trabajo(sesion)


def listar_herramientas() -> list[dict]:
    async def trabajo(s):
        r = await s.list_tools()
        return [{"nombre": t.name, "descripcion": t.description,
                 "parametros": getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)} for t in r.tools]
    return asyncio.run(_sesion(trabajo))


def llamar(nombre: str, argumentos: dict):
    """Llama una herramienta y devuelve su resultado como datos de Python."""
    async def trabajo(s):
        return await s.call_tool(nombre, argumentos)
    r = asyncio.run(_sesion(trabajo))
    texto = "\n".join(c.text for c in r.content if getattr(c, "type", "") == "text")
    if r.is_error:
        raise ErrorMCP(texto.replace(f"Error executing tool {nombre}: ", ""))
    estructurado = getattr(r, "structured_content", None)
    if estructurado is not None:
        return estructurado.get("result", estructurado) if isinstance(estructurado, dict) else estructurado
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return texto
