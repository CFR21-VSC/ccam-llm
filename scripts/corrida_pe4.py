"""Corrida única de la PE4: servidor MCP, grafo y las 5 conversaciones con su traza, en una carpeta.

QUÉ HACE
    1. Crea un sistema de gestión de cambios y una memoria del agente NUEVOS, dentro de la carpeta
       de la corrida (así la corrida no depende de lo que quedó de antes).
    2. Corre el script cliente MCP (list_tools y call_tool) y guarda su salida.
    3. Exporta el grafo en Mermaid.
    4. Corre las 5 conversaciones:
         C1 solo consulta documentos          (u_solicitante_prod)
         C2 solo consulta el sistema          (u_analista_qa)
         C3 acción aprobada                   la pausa queda guardada y se RETOMA EN OTRO PROCESO
                                              con el mismo thread_id, como pasaría al día siguiente
         C4 acción rechazada                  (rechaza u_jefe_qa)
         C5 llega al límite de pasos          (máximo 3 para esta conversación)
    5. Guarda la auditoría del sistema, medicion.md y manifiesto.json con hashes.

USO
    python -m scripts.corrida_pe4                     # con Claude (clave en .env)
    python -m scripts.corrida_pe4 --simulado          # sin clave: decisiones de un guion fijo (CI)

Las aprobaciones las da este script en nombre de u_jefe_qa: es la demostración de los dos caminos.
En uso real, la persona usa python -m scripts.agente --thread ... --aprobar/--rechazar.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langgraph.types import Command

from scripts.corrida import commit_actual, sha256

RAIZ = Path(__file__).resolve().parent.parent

CONVERSACIONES = [
    {"id": "C1", "tipo": "solo consulta documentos", "usuario": "u_solicitante_prod",
     "mensaje": "¿Qué dice el SOP-VS-003 sobre desactivar el audit trail de un sistema?"},
    {"id": "C2", "tipo": "solo consulta el sistema", "usuario": "u_analista_qa",
     "mensaje": "¿En qué estado está el CCAM-2026-108 y cuándo vence?"},
    {"id": "C3", "tipo": "acción aprobada (retomada en otro proceso)", "usuario": "u_analista_qa",
     "mensaje": "Evaluá el impacto del CCAM-2026-101 y registrá el borrador de evaluación en el sistema.",
     "aprobacion": {"decision": "aprobada", "aprobador": "u_jefe_qa", "motivo": ""}, "otro_proceso": True},
    {"id": "C4", "tipo": "acción rechazada", "usuario": "u_analista_qa",
     "mensaje": "Evaluá el CCAM-2026-108 y registrá el borrador de evaluación en el sistema.",
     "aprobacion": {"decision": "rechazada", "aprobador": "u_jefe_qa",
                    "motivo": "antes de registrar quiero la alternativa de rendimiento que proponga Sistemas"}},
    {"id": "C5", "tipo": "llega al límite de pasos", "usuario": "u_analista_qa", "max_pasos": 3,
     "mensaje": "Evaluá el impacto de todos los CCAM vencidos."},
]

# Decisiones fijas para el modo simulado (sin clave). Con Claude, decide el modelo.
GUIONES = {
    "C1": [{"accion": "buscar_documentos", "razon": "La pregunta es sobre un procedimiento.",
            "consulta": "SOP-VS-003 desactivar audit trail"},
           {"accion": "responder", "razon": "Con el fragmento alcanza.",
            "respuesta": "Según SOP-VS-003 §3.2, el audit trail de un sistema GxP no se desactiva por rendimiento."}],
    "C2": [{"accion": "consultar_ccam", "razon": "Preguntan por un CCAM puntual.", "id_ccam": "CCAM-2026-108"},
           {"accion": "responder", "razon": "Ya tengo el estado.",
            "respuesta": "El CCAM-2026-108 está abierto y vence el 2026-12-08."}],
    "C3": [{"accion": "evaluar_ccam", "razon": "Piden evaluar el impacto.", "id_ccam": "CCAM-2026-101"},
           {"accion": "registrar_evaluacion", "razon": "Piden registrar el borrador.", "id_ccam": "CCAM-2026-101"},
           {"accion": "responder", "razon": "Quedó registrado.",
            "respuesta": "Registré el borrador de evaluación del CCAM-2026-101; queda pendiente de la firma de QA."}],
    "C4": [{"accion": "evaluar_ccam", "razon": "Piden evaluar el impacto.", "id_ccam": "CCAM-2026-108"},
           {"accion": "registrar_evaluacion", "razon": "Piden registrar el borrador.", "id_ccam": "CCAM-2026-108"}],
    "C5": [{"accion": "listar_ccam", "razon": "Necesito saber cuáles están vencidos.", "estado": "vencido"},
           {"accion": "evaluar_ccam", "razon": "Evalúo el primero.", "id_ccam": "CCAM-2026-102"},
           {"accion": "evaluar_ccam", "razon": "Evalúo el segundo.", "id_ccam": "CCAM-2026-106"},
           {"accion": "evaluar_ccam", "razon": "Evalúo el tercero.", "id_ccam": "CCAM-2026-111"}],
}


def _json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def texto_traza(c: dict, r: dict) -> str:
    """La traza de una conversación, legible, para el PDF."""
    L = [f"{c['id']} · {c['tipo']} · thread_id {c['id']} · usuario {c['usuario']} · máximo {r['max_pasos']} pasos",
         f"> {c['mensaje']}", ""]
    for t in r["traza"]:
        if t["nodo"] == "decidir":
            if t.get("accion"):
                params = json.dumps(t.get("parametros", {}), ensure_ascii=False)
                L.append(f"[paso {t['paso']}] decidir   → {t['accion']} {params if params != '{}' else ''}".rstrip())
                L.append(f"                  porque: {t['razon']}")
            else:
                L.append(f"[corte] decidir   → {t.get('resultado')} ({t.get('pasos', '')} pasos)")
        elif t["nodo"] == "ejecutar":
            L.append(f"          ejecutar  → {t['accion']}: {t.get('resumen') or 'ERROR ' + t.get('detalle', '')}")
        elif t["nodo"] == "pedir_aprobacion":
            if t["resultado"] in ("aprobada", "rechazada"):
                L.append(f"          ⏸ interrupt: registrar_evaluacion {t['id_ccam']} impacto {t['impacto']} "
                         f"— esperando a QA")
                L.append(f"          ▶ {t['aprobador']}: {t['resultado'].upper()}"
                         + (f" ({t['motivo']})" if t.get("motivo") else ""))
            else:
                L.append(f"          pedir_aprobacion → no se pidió: {t.get('motivo')}")
        elif t["nodo"] == "responder":
            L.append(f"          responder ({t['motivo']})")
    L += ["", f"< {r['final']['respuesta']}", "",
          f"pasos {r['pasos']} · tokens {r['consumo'].get('tokens_entrada', 0)}/{r['consumo'].get('tokens_salida', 0)} · "
          f"USD {r['consumo'].get('costo_usd', 0):.6f} · fotos del checkpointer {r['fotos_guardadas']}"]
    return "\n".join(L)


def conversar(carpeta: Path, c: dict, simulado: bool, entorno: dict) -> dict:
    from src.agente.grafo import CONFIG, construir_agente, memoria
    from src.proveedores import ProveedorSimulado

    guion = json.loads(json.dumps(GUIONES[c["id"]]))
    proveedor = ProveedorSimulado("guion", guion=guion) if simulado else None
    max_pasos = c.get("max_pasos")
    agente = construir_agente(proveedor, memoria(), max_pasos=max_pasos)
    config = {"configurable": {"thread_id": c["id"]}}
    salida = max_pasos or CONFIG["max_pasos"]

    r = agente.invoke({"mensajes": [{"rol": "usuario", "texto": c["mensaje"]}], "usuario": c["usuario"], "pasos": 0},
                      config)
    pausa = r.get("__interrupt__")
    retomada = None
    if pausa:
        if c.get("otro_proceso"):
            # Proceso nuevo: no comparte memoria con este. Solo el thread_id y la base del checkpointer.
            args = [sys.executable, "-m", "scripts.agente", "--thread", c["id"],
                    "--aprobar", c["aprobacion"]["aprobador"]]
            env = {**entorno}
            if simulado:
                env.update(LLM_PROVIDER="simulado", SIMULADO_ESCENARIO="guion", SIMULADO_GUION=json.dumps(guion))
            p = subprocess.run(args, cwd=RAIZ, env=env, capture_output=True, text=True, encoding="utf-8",
                               timeout=600)
            retomada = {"comando": " ".join(["python"] + args[1:]), "codigo_salida": p.returncode,
                        "salida": p.stdout, "errores": p.stderr[-2000:]}
            (carpeta / "conversaciones" / f"{c['id']}_retomada.txt").write_text(
                f"$ {retomada['comando']}\n{p.stdout}", encoding="utf-8")
            agente = construir_agente(proveedor, memoria(), max_pasos=max_pasos)  # lee lo que dejó el otro proceso
            r = agente.get_state(config).values
        else:
            r = agente.invoke(Command(resume=c["aprobacion"]), config)

    estado = agente.get_state(config)
    datos = {**c, "thread_id": c["id"], "max_pasos": salida,
             "pausa": pausa[0].value if pausa else None, "retomada": retomada,
             "traza": r.get("traza", []), "mensajes": r.get("mensajes", []), "final": r.get("final"),
             "pasos": r.get("pasos"), "consumo": r.get("consumo", {}),
             "fotos_guardadas": len(list(agente.get_state_history(config))), "siguiente": list(estado.next)}
    _json(carpeta / "conversaciones" / f"{c['id']}.json", datos)
    (carpeta / "conversaciones" / f"{c['id']}.txt").write_text(texto_traza(c, datos), encoding="utf-8")
    print(f"{c['id']}: {datos['final']['motivo'] if datos['final'] else 'sin cerrar'} · {datos['pasos']} pasos",
          file=sys.stderr)
    return datos


def correr(simulado: bool = False, destino: Path | None = None) -> Path:
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    carpeta = destino or (RAIZ / "resultados" / f"corrida_pe4_{fecha}")
    carpeta.mkdir(parents=True, exist_ok=False)
    trabajo = carpeta / "_trabajo"
    trabajo.mkdir()
    os.environ["SISTEMA_CCAM_DB"] = str(trabajo / "sistema_ccam.db")
    os.environ["AGENTE_MEMORIA_DB"] = str(trabajo / "memoria_agente.db")
    entorno = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    from src import sistema
    from src.agente.grafo import construir_agente, mermaid
    from src.proveedores import ProveedorSimulado

    # 2. script cliente MCP
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        from scripts import cliente_mcp as script_cliente
        script_cliente.main()
    (carpeta / "cliente_mcp.txt").write_text("$ python -m scripts.cliente_mcp\n" + buf.getvalue(), encoding="utf-8")

    # 3. grafo
    agente = construir_agente(ProveedorSimulado("guion"))
    (carpeta / "grafo.mmd").write_text(mermaid(agente), encoding="utf-8")

    # 4. conversaciones
    resultados = [conversar(carpeta, c, simulado, entorno) for c in CONVERSACIONES]

    # 5. auditoría del sistema y medición
    _json(carpeta / "sistema_auditoria.json", sistema.auditoria())
    filas = []
    for r in resultados:
        acciones = [t["accion"] for t in r["traza"] if t["nodo"] == "decidir" and t.get("accion")]
        filas.append({"id": r["id"], "tipo": r["tipo"], "usuario": r["usuario"], "pasos": r["pasos"],
                      "max_pasos": r["max_pasos"], "acciones": acciones,
                      "aprobacion": next((t["resultado"] for t in r["traza"] if t["nodo"] == "pedir_aprobacion"), None),
                      "cierre": r["final"]["motivo"] if r["final"] else None,
                      "tokens_entrada": r["consumo"].get("tokens_entrada", 0),
                      "tokens_salida": r["consumo"].get("tokens_salida", 0),
                      "costo_usd": r["consumo"].get("costo_usd", 0), "fotos": r["fotos_guardadas"]})
    med = {"modo": "simulado" if simulado else "real", "conversaciones": filas,
           "escrituras_en_sistema": [a for a in sistema.auditoria() if a["accion"] == "registrar_evaluacion"],
           "costo_total_usd": round(sum(f["costo_usd"] for f in filas), 6)}
    _json(carpeta / "medicion.json", med)
    L = [f"# Corrida PE4 — {datetime.now():%Y-%m-%d %H:%M}", "",
         "| Conv. | Tipo | Usuario | Acciones | Aprobación | Cierre | Pasos | Tokens | USD |", "|---|---|---|---|---|---|---|---|---|"]
    for f in filas:
        L.append(f"| {f['id']} | {f['tipo']} | {f['usuario']} | {' → '.join(f['acciones'])} | {f['aprobacion'] or '—'} | "
                 f"{f['cierre']} | {f['pasos']}/{f['max_pasos']} | {f['tokens_entrada']}/{f['tokens_salida']} | {f['costo_usd']:.6f} |")
    L += ["", f"Escrituras en el sistema: {len(med['escrituras_en_sistema'])} (solo la aprobada). "
          f"Costo total: USD {med['costo_total_usd']:.6f}.", ""]
    for r in resultados:
        L += ["```", (carpeta / "conversaciones" / f"{r['id']}.txt").read_text(encoding="utf-8"), "```", ""]
    (carpeta / "medicion.md").write_text("\n".join(L), encoding="utf-8")

    for f in trabajo.iterdir():  # las bases de trabajo no son evidencia legible: se borran
        f.unlink()
    trabajo.rmdir()
    archivos = sorted(f for f in carpeta.rglob("*") if f.is_file() and f.name != "manifiesto.json")
    _json(carpeta / "manifiesto.json", {
        "corrida": carpeta.name, "fecha": datetime.now().isoformat(timespec="seconds"),
        "modo": med["modo"], "modelo": "simulado" if simulado else os.getenv("LLM_MODEL", "claude-haiku-5-5"),
        "commit": commit_actual(),
        "archivos": {str(f.relative_to(carpeta)).replace("\\", "/"): sha256(f) for f in archivos}})
    print("\n".join(L))
    return carpeta


def main() -> int:
    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser(description="Corrida única de la PE4 (agente).")
    p.add_argument("--simulado", action="store_true", help="decisiones de un guion fijo, sin clave")
    a = p.parse_args()
    correr(a.simulado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
