"""Conversar con el agente desde la terminal, con pausa para aprobación y retomada por thread_id.

USO
    # empezar (o seguir) una conversación
    python -m scripts.agente --usuario u_analista_qa --thread ccam-101 "Evaluá el CCAM-2026-101 y registrá el borrador"

    # si quedó esperando aprobación, retomarla después (aunque sea otro día, en otro proceso)
    python -m scripts.agente --thread ccam-101 --aprobar u_jefe_qa
    python -m scripts.agente --thread ccam-101 --rechazar u_jefe_qa --motivo "Falta la evaluación de Sistemas"

    # ver dónde quedó una conversación
    python -m scripts.agente --thread ccam-101 --estado

La memoria vive en datos/memoria_agente.db (o en AGENTE_MEMORIA_DB): por eso se puede cortar y retomar.
"""
from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv
from langgraph.types import Command

from src.agente.grafo import RAIZ, construir_agente, memoria


def mostrar(resultado: dict, agente, config, desde: int = 0) -> dict:
    """Imprime lo que pasó (desde el renglón 'desde' de la traza) y devuelve un resumen."""
    estado = agente.get_state(config)
    pausa = resultado.get("__interrupt__")
    for t in resultado.get("traza", [])[desde:]:
        print("  " + json.dumps(t, ensure_ascii=False))
    if pausa:
        pedido = pausa[0].value
        print("\n⏸  ESPERANDO APROBACIÓN DE QA")
        for k in ("accion", "id_ccam", "impacto", "requiere_revalidacion", "fundamento", "solicitado_por"):
            print(f"   {k}: {pedido.get(k)}")
        print(f"   justificacion: {pedido.get('justificacion', '')[:300]}")
        print(f"   → retomar con: python -m scripts.agente --thread {config['configurable']['thread_id']} "
              "--aprobar u_jefe_qa   (o --rechazar u_jefe_qa --motivo \"...\")")
        return {"estado": "esperando_aprobacion", "pendiente": pedido, "siguiente": list(estado.next)}
    final = resultado.get("final") or {}
    print(f"\n■ {final.get('motivo', '?').upper()}: {final.get('respuesta', '')}")
    print(f"  pasos: {resultado.get('pasos')} · consumo: {json.dumps(resultado.get('consumo', {}))}")
    return {"estado": "terminada", "final": final, "pasos": resultado.get("pasos"), "consumo": resultado.get("consumo")}


def main() -> int:
    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser(description="Agente supervisado del sistema CCAM (PE4).")
    p.add_argument("mensaje", nargs="?", help="Lo que le pedís al agente")
    p.add_argument("--usuario", default="u_analista_qa")
    p.add_argument("--thread", required=True, help="thread_id: el expediente de la conversación")
    p.add_argument("--max-pasos", type=int, default=None)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--aprobar", metavar="APROBADOR")
    g.add_argument("--rechazar", metavar="APROBADOR")
    g.add_argument("--estado", action="store_true")
    p.add_argument("--motivo", default="")
    a = p.parse_args()

    config = {"configurable": {"thread_id": a.thread}}
    agente = construir_agente(checkpointer=memoria(), max_pasos=a.max_pasos)

    if a.estado:
        e = agente.get_state(config)
        print(json.dumps({"siguiente": list(e.next), "pasos": e.values.get("pasos"),
                          "pendiente_aprobacion": e.values.get("pendiente_aprobacion"),
                          "final": e.values.get("final"), "fotos_guardadas": len(list(agente.get_state_history(config)))},
                         ensure_ascii=False, indent=2))
        return 0
    if a.aprobar or a.rechazar:
        if not agente.get_state(config).next:
            print(f"La conversación {a.thread} no está esperando ninguna aprobación.")
            return 1
        previo = agente.get_state(config)
        pendiente = previo.values.get("pendiente_aprobacion") or {}
        n_fotos = len(list(agente.get_state_history(config)))
        print(f"↺ Recuperado del checkpointer: thread {a.thread}, {previo.values.get('pasos')} pasos dados, "
              f"{n_fotos} fotos guardadas, detenido en {list(previo.next)}")
        print(f"  pendiente: {pendiente.get('accion')} {pendiente.get('id_ccam')} impacto {pendiente.get('impacto')} "
              f"pedido por {pendiente.get('solicitado_por')}")
        decision = {"decision": "aprobada" if a.aprobar else "rechazada",
                    "aprobador": a.aprobar or a.rechazar, "motivo": a.motivo}
        print(f"▶ Retomando con: {json.dumps(decision, ensure_ascii=False)}")
        mostrar(agente.invoke(Command(resume=decision), config), agente, config,
                desde=len(previo.values.get("traza", [])))
        return 0
    if not a.mensaje:
        p.error("falta el mensaje")
    print(f"▶ {a.usuario} · thread {a.thread}: {a.mensaje}")
    entrada = {"mensajes": [{"rol": "usuario", "texto": a.mensaje}], "usuario": a.usuario, "pasos": 0}
    mostrar(agente.invoke(entrada, config), agente, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
