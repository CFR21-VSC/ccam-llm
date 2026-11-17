"""Pruebas de la PE4 sin clave: servidor MCP, aprobación humana, límite de pasos y retomada.

El modelo se reemplaza por un guion de decisiones (ProveedorSimulado "guion"); el resto es real:
el grafo de LangGraph, el servidor MCP por stdio, la base SQLite y el RAG con embeddings simulados.
"""
import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError

from src import cliente_mcp, sistema
from src.agente.grafo import Decision, construir_agente, memoria, mermaid
from src.proveedores import ProveedorSimulado
from src.rag.buscar import Buscador
from src.rag.embeddings import EmbedderSimulado
from src.rag.ingestar import RAIZ, ingestar

EVALUAR = {"accion": "evaluar_ccam", "razon": "Piden evaluar.", "id_ccam": "CCAM-2026-101"}
REGISTRAR = {"accion": "registrar_evaluacion", "razon": "Piden registrar.", "id_ccam": "CCAM-2026-101"}
RESPONDER = {"accion": "responder", "razon": "Listo.", "respuesta": "Registré el borrador del CCAM-2026-101."}
PEDIDO = "Evaluá el CCAM-2026-101 y registrá el borrador."


@pytest.fixture(scope="module")
def buscador(tmp_path_factory):
    col = ingestar(RAIZ / "documentos", "A", destino=tmp_path_factory.mktemp("chroma"), embedder=EmbedderSimulado())
    return Buscador("A", coleccion=col, embedder=EmbedderSimulado())


@pytest.fixture(autouse=True)
def base_nueva(tmp_path, monkeypatch):
    """Cada prueba arranca con un sistema de gestión de cambios recién creado."""
    monkeypatch.setenv("SISTEMA_CCAM_DB", str(tmp_path / "sistema.db"))


@pytest.fixture(scope="module")
def herramientas_mcp():
    return cliente_mcp.listar_herramientas()  # el servidor real, por stdio


def agente_con(guion, buscador, herramientas_mcp, checkpointer=None, max_pasos=None):
    return construir_agente(ProveedorSimulado("guion", guion=[dict(d) for d in guion]),
                            checkpointer or InMemorySaver(), max_pasos=max_pasos,
                            buscador=buscador, herramientas_mcp=herramientas_mcp)


def iniciar(agente, thread, usuario="u_analista_qa", mensaje=PEDIDO):
    config = {"configurable": {"thread_id": thread}}
    return agente.invoke({"mensajes": [{"rol": "usuario", "texto": mensaje}], "usuario": usuario, "pasos": 0},
                         config), config


def escrituras():
    return [a for a in sistema.auditoria() if a["accion"] == "registrar_evaluacion"]


# ---------------------------------------------------------------- servidor MCP
def test_servidor_lista_tres_herramientas_tipadas(herramientas_mcp):
    nombres = {h["nombre"]: h for h in herramientas_mcp}
    assert set(nombres) == {"consultar_ccam", "listar_ccam", "registrar_evaluacion"}
    assert "Solo lectura" in nombres["consultar_ccam"]["descripcion"]
    assert "ESCRITURA" in nombres["registrar_evaluacion"]["descripcion"]
    props = nombres["registrar_evaluacion"]["parametros"]["properties"]
    assert props["impacto"]["enum"] == ["sin_impacto", "menor", "mayor", "critico"]
    assert "pattern" in props["id_ccam"]


def test_servidor_llama_y_valida():
    assert cliente_mcp.llamar("consultar_ccam", {"id_ccam": "CCAM-2026-108"})["estado"] == "abierto"
    with pytest.raises(cliente_mcp.ErrorMCP, match="No existe"):
        cliente_mcp.llamar("consultar_ccam", {"id_ccam": "CCAM-2026-999"})
    with pytest.raises(cliente_mcp.ErrorMCP):
        cliente_mcp.llamar("consultar_ccam", {"id_ccam": "108"})  # parámetro fuera de patrón


@pytest.mark.parametrize("solicita,aprueba,motivo", [
    ("u_analista_qa", "u_analista_qa", "no es QA formal"),
    ("u_jefe_qa", "u_jefe_qa", "segregación"),
    ("u_solicitante_prod", "u_jefe_qa", "no tiene un rol"),
])
def test_sistema_rechaza_aprobaciones_invalidas(solicita, aprueba, motivo):
    with pytest.raises(sistema.ErrorSistema, match=motivo):
        sistema.registrar_evaluacion("CCAM-2026-108", "critico", False, ["SOP-VS-003 §3.2"],
                                     "Prueba de control.", solicita, aprueba)
    assert escrituras() == []


# ---------------------------------------------------------------- decisión cerrada
def test_decision_exige_sus_parametros():
    with pytest.raises(ValidationError, match="necesita el campo id_ccam"):
        Decision(accion="evaluar_ccam", razon="Sin número.")
    with pytest.raises(ValidationError):
        Decision(accion="borrar_ccam", razon="No existe esa acción.", id_ccam="CCAM-2026-101")


# ---------------------------------------------------------------- aprobación humana: los dos caminos
def test_escritura_aprobada_se_ejecuta(buscador, herramientas_mcp):
    agente = agente_con([EVALUAR, REGISTRAR, RESPONDER], buscador, herramientas_mcp)
    r, config = iniciar(agente, "aprobada")
    pausa = r["__interrupt__"][0].value
    assert pausa["accion"] == "registrar_evaluacion" and pausa["id_ccam"] == "CCAM-2026-101"
    assert pausa["impacto"] and pausa["fundamento"] and pausa["solicitado_por"] == "u_analista_qa"
    assert escrituras() == [], "nada se escribe antes de aprobar"
    assert agente.get_state(config).values["pendiente_aprobacion"]["id_ccam"] == "CCAM-2026-101"

    r = agente.invoke(Command(resume={"decision": "aprobada", "aprobador": "u_jefe_qa"}), config)
    assert r["final"]["motivo"] == "resuelto"
    assert len(escrituras()) == 1
    assert sistema.consultar("CCAM-2026-101")["estado"] == "borrador_registrado"


def test_escritura_rechazada_no_se_ejecuta_y_se_cuenta(buscador, herramientas_mcp):
    agente = agente_con([EVALUAR, REGISTRAR], buscador, herramientas_mcp)
    _, config = iniciar(agente, "rechazada")
    r = agente.invoke(Command(resume={"decision": "rechazada", "aprobador": "u_jefe_qa", "motivo": "falta información"}),
                      config)
    assert r["final"]["motivo"] == "rechazado"
    assert "No registré nada" in r["final"]["respuesta"] and "falta información" in r["final"]["respuesta"]
    assert escrituras() == []


@pytest.mark.parametrize("aprobador", ["u_analista_qa", "u_validaciones"])
def test_aprobacion_de_quien_pidio_o_de_no_qa_vale_como_rechazo(buscador, herramientas_mcp, aprobador):
    agente = agente_con([EVALUAR, REGISTRAR], buscador, herramientas_mcp)
    _, config = iniciar(agente, f"invalida-{aprobador}")
    r = agente.invoke(Command(resume={"decision": "aprobada", "aprobador": aprobador}), config)
    assert r["final"]["motivo"] == "rechazado" and "aprobación inválida" in r["final"]["respuesta"]
    assert escrituras() == []


def test_un_solicitante_no_puede_pedir_el_registro(buscador, herramientas_mcp):
    agente = agente_con([EVALUAR, REGISTRAR], buscador, herramientas_mcp)
    r, _ = iniciar(agente, "solicitante", usuario="u_solicitante_prod")
    assert "__interrupt__" not in r, "no se le pide firma a QA por algo que no se puede hacer"
    assert r["final"]["motivo"] == "rechazado" and escrituras() == []


def test_registrar_sin_evaluar_no_pide_aprobacion(buscador, herramientas_mcp):
    agente = agente_con([REGISTRAR, RESPONDER], buscador, herramientas_mcp)
    r, _ = iniciar(agente, "sin-evaluar")
    assert "__interrupt__" not in r
    assert any(t["nodo"] == "pedir_aprobacion" and t["resultado"] == "no se pidió" for t in r["traza"])
    assert escrituras() == []


# ---------------------------------------------------------------- bucle con límite
def test_limite_de_pasos_termina_con_mensaje(buscador, herramientas_mcp):
    consultar = {"accion": "consultar_ccam", "razon": "Consulto.", "id_ccam": "CCAM-2026-102"}
    agente = agente_con([consultar] * 5, buscador, herramientas_mcp, max_pasos=2)
    r, _ = iniciar(agente, "limite", mensaje="Revisá todos los vencidos.")
    assert r["pasos"] == 2 and r["final"]["motivo"] == "limite_de_pasos"
    assert "máximo de 2 pasos" in r["final"]["respuesta"]


def test_solo_consulta_no_pasa_por_aprobacion(buscador, herramientas_mcp):
    consultar = {"accion": "consultar_ccam", "razon": "Consulto.", "id_ccam": "CCAM-2026-108"}
    fin = {"accion": "responder", "razon": "Listo.", "respuesta": "El CCAM-2026-108 está abierto."}
    agente = agente_con([consultar, fin], buscador, herramientas_mcp)
    r, _ = iniciar(agente, "consulta", mensaje="¿Cómo está el CCAM-2026-108?")
    assert [t["nodo"] for t in r["traza"]] == ["decidir", "ejecutar", "decidir", "responder"]


# ---------------------------------------------------------------- estado persistente
def test_retomar_con_el_mismo_thread_id_desde_otra_instancia(buscador, herramientas_mcp, tmp_path):
    ruta = tmp_path / "memoria.db"
    primero = agente_con([EVALUAR, REGISTRAR], buscador, herramientas_mcp, checkpointer=memoria(ruta))
    _, config = iniciar(primero, "ccam-101")
    del primero  # "se cierra el programa"

    segundo = agente_con([RESPONDER], buscador, herramientas_mcp, checkpointer=memoria(ruta))
    estado = segundo.get_state(config)
    assert estado.next == ("pedir_aprobacion",) and estado.values["pasos"] == 2
    r = segundo.invoke(Command(resume={"decision": "aprobada", "aprobador": "u_jefe_qa"}), config)
    assert r["final"]["motivo"] == "resuelto" and len(escrituras()) == 1
    assert [t["accion"] for t in r["traza"] if t["nodo"] == "ejecutar"] == ["evaluar_ccam", "registrar_evaluacion"]


def test_grafo_en_mermaid(buscador, herramientas_mcp):
    texto = mermaid(agente_con([], buscador, herramientas_mcp))
    for nodo in ("decidir", "ejecutar", "pedir_aprobacion", "responder"):
        assert nodo in texto
