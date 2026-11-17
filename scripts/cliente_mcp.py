"""Script cliente: prueba el servidor MCP solo, sin el agente.

    python -m scripts.cliente_mcp

1. Arranca el servidor (src/mcp_servidor.py) por stdio.
2. Lista sus herramientas con descripción y parámetros (list_tools).
3. Llama a consultar_ccam con un CCAM que existe y con uno que no (call_tool).
4. Prueba que el servidor rechaza una escritura donde quien pide también aprueba.

EQUIVALENTE GxP
    La prueba de interfaz: verificar el sistema por su puerta antes de conectarle nada.
"""
from __future__ import annotations

import json
import sys

from src import cliente_mcp


def main() -> int:
    print("$ list_tools")
    for h in cliente_mcp.listar_herramientas():
        print(f"\n● {h['nombre']}")
        print("  " + " ".join(h["descripcion"].split()))
        props = (h["parametros"] or {}).get("properties", {})
        requeridos = set((h["parametros"] or {}).get("required", []))
        for nombre, esquema in props.items():
            tipo = esquema.get("type") or ("enum" if "enum" in esquema else "")
            extra = esquema.get("enum") or esquema.get("pattern") or ""
            print(f"    - {nombre}: {tipo}{' ' + json.dumps(extra, ensure_ascii=False) if extra else ''}"
                  f"{' (obligatorio)' if nombre in requeridos else ''}")

    print('\n$ call_tool consultar_ccam {"id_ccam": "CCAM-2026-108"}')
    r = cliente_mcp.llamar("consultar_ccam", {"id_ccam": "CCAM-2026-108"})
    print(json.dumps({k: (v[:90] + "…" if isinstance(v, str) and len(v) > 90 else v) for k, v in r.items()},
                     ensure_ascii=False, indent=2))

    print('\n$ call_tool consultar_ccam {"id_ccam": "CCAM-2026-999"}')
    try:
        cliente_mcp.llamar("consultar_ccam", {"id_ccam": "CCAM-2026-999"})
    except cliente_mcp.ErrorMCP as exc:
        print(f"error: {exc}")

    print('\n$ call_tool registrar_evaluacion {... "solicitado_por": "u_jefe_qa", "aprobado_por": "u_jefe_qa"}')
    try:
        cliente_mcp.llamar("registrar_evaluacion", {
            "id_ccam": "CCAM-2026-108", "impacto": "critico", "requiere_revalidacion": False,
            "fundamento": ["SOP-VS-003 §3.2"], "justificacion": "Prueba de interfaz: no debe registrarse.",
            "solicitado_por": "u_jefe_qa", "aprobado_por": "u_jefe_qa"})
    except cliente_mcp.ErrorMCP as exc:
        print(f"error: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
