"""Agente supervisado (PE4): un grafo de LangGraph que decide, actúa y pide permiso.

EL GRAFO
    START → decidir ─┬─ consulta o evaluación ──→ ejecutar ──→ decidir (bucle)
                     ├─ escritura ──→ pedir_aprobacion ─┬─ aprobada ──→ ejecutar
                     │                                  └─ rechazada ─→ responder
                     └─ responder, límite de pasos o error ──→ responder → END

LAS PIEZAS
    Estado        la "pizarra" que viaja entre nodos: mensajes, usuario, pasos,
                  pendiente_aprobacion, evaluaciones hechas, traza y consumo.
    decidir       Claude elige UNA acción. La elección es un formulario cerrado
                  (clase Decision) validado con Pydantic y con un reintento.
    ejecutar      corre la acción: el RAG de la PE3, el motor, o el servidor MCP.
    pedir_aprobacion  interrupt(): el grafo se pausa y muestra qué va a escribir.
                  Solo sigue si aprueba QA formal (rol jefe_qa) y no es quien pidió.
    responder     cierra contando qué se hizo o por qué no.
    Checkpointer  guarda el estado después de cada paso (SQLite): la conversación
                  se retoma con el mismo thread_id, incluso desde otro proceso.

EQUIVALENTE GxP
    Un analista que trabaja un expediente: consulta, evalúa, prepara el
    borrador y lo deja sobre el escritorio de QA. Nada se registra sin firma.
"""
from __future__ import annotations

import json
import operator
import sqlite3
from pathlib import Path
from string import Template
from typing import Annotated, Literal, Optional, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src import cliente_mcp
from src.motor import herramienta_salida, llamar_con_reintento
from src.proveedores import ErrorProveedor, Proveedor, crear_proveedor
from src.rag.buscar import Buscador, roles_de
from src.rag.buscar import buscar as buscar_rag

RAIZ = Path(__file__).resolve().parent.parent.parent
CONFIG = json.loads((RAIZ / "config" / "agente.json").read_text(encoding="utf-8"))
ESCRITURAS = {"registrar_evaluacion"}
ESTADOS_CCAM = ("abierto", "en_evaluacion", "borrador_registrado", "vencido", "cerrado")

# Acciones propias del agente (no están en el servidor MCP). Las del MCP traen su
# descripción del propio servidor (list_tools): una sola fuente de verdad.
LOCALES = {
    "buscar_documentos": "buscar_documentos(consulta): busca en los procedimientos y documentos del laboratorio "
                         "que el usuario puede leer y devuelve los fragmentos con su código y sección.",
    "evaluar_ccam": "evaluar_ccam(id_ccam): propone la evaluación de impacto GxP de un CCAM con el motor y los "
                    "documentos (impacto, revalidación, fundamento y tareas). No escribe nada en el sistema.",
    "responder": "responder(respuesta): termina la conversación con la respuesta final para la persona.",
}


# ------------------------------------------------------------ la decisión, como formulario cerrado
class Decision(BaseModel):
    """Lo que devuelve el nodo decidir. Cerrado: el modelo no puede inventar una acción."""
    model_config = ConfigDict(extra="forbid")

    accion: Literal["buscar_documentos", "consultar_ccam", "listar_ccam", "evaluar_ccam",
                    "registrar_evaluacion", "responder"]
    razon: str = Field(..., min_length=5, max_length=300, description="Por qué esta acción, en una frase")
    consulta: Optional[str] = Field(None, min_length=5, max_length=300, description="Solo para buscar_documentos")
    id_ccam: Optional[str] = Field(None, pattern=r"^CCAM-\d{4}-\d{3,4}$",
                                   description="Para consultar_ccam, evaluar_ccam y registrar_evaluacion")
    estado: Optional[Literal["abierto", "en_evaluacion", "borrador_registrado", "vencido", "cerrado"]] = Field(
        None, description="Solo para listar_ccam")
    respuesta: Optional[str] = Field(None, min_length=10, max_length=1500, description="Solo para responder")

    @model_validator(mode="after")
    def parametros(self) -> "Decision":
        falta = {"buscar_documentos": "consulta", "consultar_ccam": "id_ccam", "evaluar_ccam": "id_ccam",
                 "registrar_evaluacion": "id_ccam", "listar_ccam": "estado", "responder": "respuesta"}[self.accion]
        if getattr(self, falta) is None:
            raise ValueError(f"la acción {self.accion} necesita el campo {falta}")
        return self


# ------------------------------------------------------------ el estado
def _sumar(a: dict, b: dict) -> dict:
    return {k: round((a or {}).get(k, 0) + (b or {}).get(k, 0), 6) for k in set(a or {}) | set(b or {})}


def _fusionar(a: dict, b: dict) -> dict:
    return {**(a or {}), **(b or {})}


class Estado(TypedDict, total=False):
    mensajes: Annotated[list[dict], operator.add]     # la conversación; se acumula, no se pisa
    usuario: str
    pasos: int
    pendiente_aprobacion: Optional[dict]               # la escritura que espera firma
    decision: Optional[dict]
    evaluaciones: Annotated[dict, _fusionar]           # id_ccam → propuesta del motor
    traza: Annotated[list[dict], operator.add]         # un renglón por nodo, para la evidencia
    consumo: Annotated[dict, _sumar]                   # tokens y costo de todas las llamadas
    final: Optional[dict]


def _msg(rol: str, texto: str) -> dict:
    return {"rol": rol, "texto": texto}


def _traza(nodo: str, **detalle) -> dict:
    return {"nodo": nodo, **detalle}


# ------------------------------------------------------------ construcción
def describir_herramientas(herramientas_mcp: list[dict]) -> str:
    lineas = [f"- {LOCALES['buscar_documentos']}", f"- {LOCALES['evaluar_ccam']}"]
    for h in herramientas_mcp:
        if h["nombre"] == "registrar_evaluacion":
            lineas.append(f"- registrar_evaluacion(id_ccam): {h['descripcion']} Vos indicás solo el id_ccam: "
                          "el borrador sale de tu evaluar_ccam de esta conversación.")
        else:
            params = ", ".join((h.get("parametros") or {}).get("properties", {}).keys())
            lineas.append(f"- {h['nombre']}({params}): {' '.join(h['descripcion'].split())}")
    lineas.append(f"- {LOCALES['responder']}")
    return "\n".join(lineas)


def construir_agente(proveedor: Optional[Proveedor] = None, checkpointer=None, max_pasos: Optional[int] = None,
                     buscador: Optional[Buscador] = None, herramientas_mcp: Optional[list[dict]] = None):
    """Arma y compila el grafo. Todo se puede inyectar para las pruebas."""
    from src.rag.responder import responder as responder_rag  # importa ChromaDB solo si hace falta

    max_pasos = max_pasos or CONFIG["max_pasos"]
    herramientas_mcp = herramientas_mcp if herramientas_mcp is not None else cliente_mcp.listar_herramientas()
    sistema_txt = Template((RAIZ / "prompts" / "agente.md").read_text(encoding="utf-8")).substitute(
        herramientas=describir_herramientas(herramientas_mcp), max_pasos=max_pasos)
    herramienta = herramienta_salida(Decision, nombre="decidir_paso",
                                     descripcion="Elige la próxima acción del agente con sus parámetros.")

    def _proveedor() -> Proveedor:
        nonlocal proveedor
        proveedor = proveedor or crear_proveedor()
        return proveedor

    # ---------------- nodo decidir
    def decidir(estado: Estado) -> dict:
        pasos = estado.get("pasos", 0)
        if pasos >= max_pasos:
            return {"decision": {"accion": "limite"}, "traza": [_traza("decidir", resultado="límite de pasos", pasos=pasos)]}
        transcripcion = "\n".join(f"[{m['rol']}] {m['texto']}" for m in estado.get("mensajes", []))
        turno = (f"Usuario: {estado['usuario']} (rol {', '.join(roles_de(estado['usuario'])) or 'desconocido'})\n"
                 f"Paso {pasos + 1} de {max_pasos}.\n\nConversación hasta ahora:\n{transcripcion}")
        try:
            d, error, metricas = llamar_con_reintento(_proveedor(), sistema_txt, turno, herramienta, Decision)
        except ErrorProveedor as exc:
            d, error, metricas = None, None, None
            error_txt = exc.mensaje
        else:
            error_txt = error.mensaje if error else ""
        consumo = {"tokens_entrada": metricas.input_tokens, "tokens_salida": metricas.output_tokens,
                   "costo_usd": metricas.cost, "llamadas": metricas.intentos} if metricas else {}
        if d is None:
            return {"pasos": pasos + 1, "decision": {"accion": "error", "detalle": error_txt}, "consumo": consumo,
                    "traza": [_traza("decidir", paso=pasos + 1, resultado="error", detalle=error_txt)]}
        params = {k: v for k, v in d.model_dump(exclude_none=True).items() if k not in ("accion", "razon", "respuesta")}
        cambios: dict = {"pasos": pasos + 1, "decision": d.model_dump(), "consumo": consumo,
                         "traza": [_traza("decidir", paso=pasos + 1, accion=d.accion, parametros=params, razon=d.razon)]}
        if d.accion != "responder":
            cambios["mensajes"] = [_msg("agente", f"Paso {pasos + 1}: {d.accion}({json.dumps(params, ensure_ascii=False)}). {d.razon}")]
        if d.accion in ESCRITURAS:
            cambios["pendiente_aprobacion"] = _preparar_escritura(estado, d)
        return cambios

    def _preparar_escritura(estado: Estado, d: Decision) -> Optional[dict]:
        ev = (estado.get("evaluaciones") or {}).get(d.id_ccam)
        if not ev or not ev.get("impacto"):
            return None
        return {"accion": "registrar_evaluacion", "id_ccam": d.id_ccam, "impacto": ev["impacto"],
                "requiere_revalidacion": ev["requiere_revalidacion"], "fundamento": ev["fundamento"],
                "justificacion": ev["justificacion"], "solicitado_por": estado["usuario"]}

    def despues_de_decidir(estado: Estado) -> str:
        accion = estado["decision"]["accion"]
        if accion in ("responder", "limite", "error"):
            return "responder"
        if accion in ESCRITURAS:
            return "pedir_aprobacion"
        return "ejecutar"

    # ---------------- nodo pedir_aprobacion
    def pedir_aprobacion(estado: Estado) -> dict:
        pendiente = estado.get("pendiente_aprobacion")
        usuario = estado["usuario"]
        # controles previos: no se le pide firma a nadie por algo que igual no se puede hacer
        if not set(roles_de(usuario)) & set(CONFIG["roles_que_pueden_pedir_registro"]):
            motivo = f"{usuario} no tiene un rol que pueda pedir el registro de una evaluación."
            return {"pendiente_aprobacion": None, "decision": {"accion": "rechazada", "motivo": motivo},
                    "traza": [_traza("pedir_aprobacion", resultado="no se pidió", motivo=motivo)]}
        if pendiente is None:
            motivo = (f"no hay una evaluación con clasificación del {estado['decision'].get('id_ccam')} en esta "
                      "conversación; primero hay que evaluarlo (o el motor derivó el caso a QA).")
            return {"pendiente_aprobacion": None,
                    "mensajes": [_msg("herramienta", f"registrar_evaluacion no se pidió: {motivo}")],
                    "decision": {"accion": "volver"},
                    "traza": [_traza("pedir_aprobacion", resultado="no se pidió", motivo=motivo)]}

        # la pausa: el grafo se detiene acá hasta que alguien responda con Command(resume=...)
        respuesta = interrupt({"pregunta": "¿Aprobás esta escritura en el sistema de gestión de cambios?",
                               **pendiente})

        decision = str(respuesta.get("decision", "")).lower()
        aprobador = respuesta.get("aprobador", "")
        motivo = respuesta.get("motivo", "")
        if decision == "aprobada":
            if CONFIG["rol_aprobador"] not in roles_de(aprobador):
                decision, motivo = "rechazada", f"aprobación inválida: {aprobador} no es QA formal ({CONFIG['rol_aprobador']})"
            elif aprobador == usuario:
                decision, motivo = "rechazada", "aprobación inválida: quien pidió el registro no puede aprobarlo"
        firmado = {**pendiente, "decision": decision if decision == "aprobada" else "rechazada",
                   "aprobador": aprobador, "motivo": motivo}
        return {"pendiente_aprobacion": firmado,
                "decision": {**estado["decision"], "aprobacion": firmado["decision"]},
                "mensajes": [_msg("aprobacion", f"{aprobador or 'sin aprobador'}: {firmado['decision']}"
                                                + (f" ({motivo})" if motivo else ""))],
                "traza": [_traza("pedir_aprobacion", resultado=firmado["decision"], aprobador=aprobador, motivo=motivo,
                                 accion=pendiente["accion"], id_ccam=pendiente["id_ccam"],
                                 impacto=pendiente["impacto"])]}

    def despues_de_aprobar(estado: Estado) -> str:
        d = estado["decision"]
        if d.get("accion") == "volver":
            return "decidir"
        return "ejecutar" if d.get("aprobacion") == "aprobada" else "responder"

    # ---------------- nodo ejecutar
    def ejecutar(estado: Estado) -> dict:
        d = estado["decision"]
        accion, usuario = d["accion"], estado["usuario"]
        cambios: dict = {}
        try:
            if accion == "buscar_documentos":
                frags = buscar_rag(d["consulta"], usuario, CONFIG["fragmentos_por_busqueda"], buscador)
                resultado = [{"fuente": f"{f['documento']} §{f['seccion']}", "fragmento": f["fragmento_id"],
                              "texto": f["texto"].split("\n", 1)[-1][:700]} for f in frags] or "sin resultados autorizados"
                resumen = f"{len(frags)} fragmentos: " + ", ".join(f["fragmento_id"] for f in frags)
            elif accion == "consultar_ccam":
                resultado = cliente_mcp.llamar("consultar_ccam", {"id_ccam": d["id_ccam"]})
                resumen = f"{d['id_ccam']}: estado {resultado['estado']}"
            elif accion == "listar_ccam":
                resultado = cliente_mcp.llamar("listar_ccam", {"estado": d["estado"]})
                resumen = f"{len(resultado)} CCAM en estado {d['estado']}"
            elif accion == "evaluar_ccam":
                ccam = cliente_mcp.llamar("consultar_ccam", {"id_ccam": d["id_ccam"]})
                entrada = {k: ccam[k] for k in ("id_ccam", "tipo_cambio", "area_solicitante",
                                                "sistema_afectado", "descripcion")}
                r = responder_rag(entrada, usuario, _proveedor(), buscador)
                if r.metricas:
                    cambios["consumo"] = {"tokens_entrada": r.metricas.input_tokens,
                                          "tokens_salida": r.metricas.output_tokens,
                                          "costo_usd": r.metricas.cost, "llamadas": r.metricas.intentos}
                if not r.ok:
                    raise RuntimeError(f"el motor no pudo evaluar: {r.error.error} ({r.error.mensaje})")
                p = r.propuesta
                ev = {"impacto": p.impacto_gxp.value if p.impacto_gxp else None,
                      "requiere_revalidacion": p.requiere_revalidacion, "requiere_humano": p.requiere_humano,
                      "fuera_de_alcance": p.fuera_de_alcance,
                      "fundamento": [f"{c.codigo} §{c.seccion}" for c in p.fundamento],
                      "justificacion": p.justificacion, "tareas": [t.descripcion for t in p.tareas],
                      "trace_id_motor": r.trace_id}
                cambios["evaluaciones"] = {d["id_ccam"]: ev}
                resultado = ev
                resumen = (f"{d['id_ccam']}: impacto {ev['impacto'] or 'sin clasificar'}"
                           + (" (requiere humano)" if ev["requiere_humano"] else "")
                           + f", fundamento {', '.join(ev['fundamento']) or '—'}")
            elif accion == "registrar_evaluacion":
                p = estado["pendiente_aprobacion"]
                if not p or p.get("decision") != "aprobada":  # defensa: nunca escribir sin firma
                    raise RuntimeError("escritura sin aprobación: no se ejecuta")
                resultado = cliente_mcp.llamar("registrar_evaluacion", {
                    k: p[k] for k in ("id_ccam", "impacto", "requiere_revalidacion", "fundamento",
                                      "justificacion", "solicitado_por")} | {"aprobado_por": p["aprobador"]})
                resumen = f"registrado {p['id_ccam']} ({p['impacto']}), aprobó {p['aprobador']}"
                cambios["pendiente_aprobacion"] = None
            else:
                raise RuntimeError(f"acción desconocida {accion}")
            texto = json.dumps(resultado, ensure_ascii=False)
            cambios["mensajes"] = [_msg("herramienta", f"{accion} → {texto[:3500]}")]
            cambios["traza"] = [_traza("ejecutar", accion=accion, resultado="ok", resumen=resumen)]
        except (cliente_mcp.ErrorMCP, RuntimeError, FileNotFoundError) as exc:
            cambios["mensajes"] = [_msg("herramienta", f"{accion} → ERROR: {exc}")]
            cambios["traza"] = [_traza("ejecutar", accion=accion, resultado="error", detalle=str(exc))]
        return cambios

    # ---------------- nodo responder
    def responder(estado: Estado) -> dict:
        d = estado.get("decision") or {}
        accion = d.get("accion")
        if accion == "responder":
            texto, motivo = d["respuesta"], "resuelto"
        elif accion == "limite":
            hechas = [t for t in estado.get("traza", []) if t["nodo"] == "ejecutar" and t.get("resultado") == "ok"]
            texto = (f"Llegué al máximo de {max_pasos} pasos sin terminar. Alcancé a hacer: "
                     + ("; ".join(t["resumen"] for t in hechas) or "nada")
                     + ". Lo que falta queda para que lo revise una persona.")
            motivo = "limite_de_pasos"
        elif d.get("aprobacion") == "rechazada" or accion == "rechazada":
            p = estado.get("pendiente_aprobacion") or {}
            quien = p.get("aprobador") or "QA"
            texto = (f"No registré nada en el sistema: {quien} rechazó el registro del borrador "
                     f"del {p.get('id_ccam', d.get('id_ccam', 'CCAM'))}"
                     + (f" ({p.get('motivo') or d.get('motivo')})" if (p.get('motivo') or d.get('motivo')) else "")
                     + ". La evaluación propuesta quedó solo en esta conversación.")
            motivo = "rechazado"
        else:
            texto = f"No pude completar el pedido: {d.get('detalle', 'error del modelo')}. Queda para revisión manual."
            motivo = "error"
        return {"final": {"motivo": motivo, "respuesta": texto}, "mensajes": [_msg("agente", texto)],
                "traza": [_traza("responder", motivo=motivo)]}

    g = StateGraph(Estado)
    g.add_node("decidir", decidir)
    g.add_node("ejecutar", ejecutar)
    g.add_node("pedir_aprobacion", pedir_aprobacion)
    g.add_node("responder", responder)
    g.add_edge(START, "decidir")
    g.add_conditional_edges("decidir", despues_de_decidir, ["ejecutar", "pedir_aprobacion", "responder"])
    g.add_conditional_edges("pedir_aprobacion", despues_de_aprobar, ["ejecutar", "responder", "decidir"])
    g.add_edge("ejecutar", "decidir")
    g.add_edge("responder", END)
    return g.compile(checkpointer=checkpointer)


def memoria(ruta: Optional[Path] = None) -> SqliteSaver:
    """El checkpointer: una base SQLite con una foto del estado por paso y por thread_id."""
    import os
    ruta = ruta or Path(os.getenv("AGENTE_MEMORIA_DB", str(RAIZ / "datos" / "memoria_agente.db")))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(str(ruta), check_same_thread=False))


def mermaid(agente) -> str:
    return agente.get_graph().draw_mermaid()
