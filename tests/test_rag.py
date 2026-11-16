"""Pruebas de la PE3 sin gastar tokens ni descargar modelos: permisos, búsqueda, citas y respuesta.

Usan los documentos reales de documentos/ con embeddings SIMULADOS (determinísticos).
No miden calidad de búsqueda (eso lo hace scripts/corrida_pe3.py con el modelo real):
prueban que los controles funcionan.
"""
import json

import pytest
from pydantic import ValidationError

from src.contrato import Salida
from src.proveedores import ProveedorSimulado
from src.rag.buscar import Buscador, rrf, tokenizar
from src.rag.corpus import ROLES, fragmentar, leer_carpeta
from src.rag.embeddings import EmbedderSimulado
from src.rag.ingestar import CONFIG_RAG, RAIZ, ingestar
from src.rag.responder import responder, responder_pregunta

DOCS = RAIZ / "documentos"
SOPS = {"SOP-CC-001", "SOP-VS-002", "SOP-VS-003", "SOP-DC-004", "SOP-EQ-005", "SOP-PR-006", "SOP-AC-007"}
VISIBLES = {  # lo que cada rol tiene que ver, ni más ni menos (pedido PE3 §2)
    "u_solicitante_prod": SOPS,
    "u_analista_qa": SOPS | {"INF-AUD-2026-03"},
    "u_validaciones": SOPS | {"EXP-VAL-CROM-01"},
    "u_jefe_qa": SOPS | {"INF-AUD-2026-03", "EXP-VAL-CROM-01", "HAL-INSP-2026-01"},
}
ENTRADA = {"id_ccam": "CCAM-2026-301", "tipo_cambio": "configuracion_sistema", "area_solicitante": "garantia_calidad",
           "sistema_afectado": "LIMS",
           "descripcion": "Responder los hallazgos de la inspección regulatoria de agosto de 2026 sobre la revisión "
                          "del audit trail del LIMS antes de aprobar resultados de valoración."}


@pytest.fixture(scope="module")
def buscador(tmp_path_factory):
    destino = tmp_path_factory.mktemp("chroma")
    col = ingestar(DOCS, "A", destino=destino, embedder=EmbedderSimulado())
    return Buscador("A", coleccion=col, embedder=EmbedderSimulado())


@pytest.fixture
def sin_umbral(monkeypatch):
    """Con embeddings simulados la similitud no es comparable: se baja el umbral para que llegue al modelo."""
    monkeypatch.setitem(CONFIG_RAG, "umbral_similitud", 0.0)


# ---------------------------------------------------------------- ingesta y metadatos
def test_ingesta_un_comando_con_metadatos(buscador):
    datos = buscador.coleccion.get(include=["metadatas"])
    assert datos["ids"], "la ingesta no dejó fragmentos"
    encabezados = {d.codigo: d for d in leer_carpeta(DOCS)}
    for m in datos["metadatas"]:
        for campo in ("documento", "titulo", "seccion", "version", "fragmento_id", "chunk_index", "hash_documento"):
            assert m[campo] not in (None, ""), campo
        doc = encabezados[m["documento"]]
        assert m["hash_documento"] == doc.hash
        assert {r for r in ROLES if m[f"rol_{r}"]} == set(doc.roles)


def test_fragmentos_con_prefijo_y_tamano():
    for doc in leer_carpeta(DOCS):
        for f in fragmentar(doc, 400, 0.10):
            assert f.texto.startswith(f"{doc.codigo} · {doc.titulo} · §{f.seccion}")
            assert f.tokens <= 400


# ---------------------------------------------------------------- permisos: una prueba por rol
@pytest.mark.parametrize("usuario", sorted(VISIBLES))
def test_cada_rol_ve_lo_suyo_y_nada_mas(buscador, usuario):
    vistos = set()
    for consulta in ("hallazgos de inspección", "CAPA-2026-041 auditoría", "HPLC-QC-03 expediente de validación",
                     "control de cambios", "audit trail"):
        vistos |= {f["documento"] for f in buscador.buscar(consulta, usuario, k=50)}
    assert vistos == VISIBLES[usuario]


def test_testigo_no_llega_ni_a_resultados_ni_al_prompt(buscador, sin_umbral):
    """La prueba clave de la rúbrica: un solicitante no recibe nada de HAL-INSP-2026-01, ni en el prompt."""
    resultados = buscador.buscar("TESTIGO-INSP-2290 hallazgos de la inspección regulatoria", "u_solicitante_prod", k=50)
    assert all(f["documento"] != "HAL-INSP-2026-01" for f in resultados)
    assert all("TESTIGO-INSP-2290" not in f["texto"] for f in resultados)

    simulado = ProveedorSimulado("rag_valido")
    r = responder(ENTRADA, "u_solicitante_prod", simulado, buscador)
    assert simulado.ultimo_prompt, "el modelo no fue llamado: la prueba no probaría nada"
    assert "TESTIGO-INSP-2290" not in simulado.ultimo_prompt
    assert "HAL-INSP-2026-01" not in simulado.ultimo_prompt
    assert all(f.documento != "HAL-INSP-2026-01" for f in r.fuentes)

    # control positivo: el jefe de QA sí lo recibe (si no, la prueba de arriba pasaría por casualidad)
    simulado_jefe = ProveedorSimulado("rag_valido")
    responder(ENTRADA, "u_jefe_qa", simulado_jefe, buscador)
    assert "TESTIGO-INSP-2290" in simulado_jefe.ultimo_prompt


def test_usuario_desconocido_no_recibe_nada(buscador):
    assert buscador.buscar("audit trail", "u_intruso", k=10) == []
    r = responder(ENTRADA, "u_intruso", ProveedorSimulado("rag_valido"), buscador)
    assert not r.ok and r.error.error == "acceso_denegado" and r.fuentes == []
    ultimo = (RAIZ / "logs" / "busquedas.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1]
    assert json.loads(ultimo)["evento"] == "acceso_denegado"


def test_bm25_no_puntua_lo_no_autorizado(buscador):
    assert buscador.buscar_bm25("CAPA-2026-041", ["solicitante"]) == []
    assert buscador.buscar_bm25("CAPA-2026-041", ["analista_qa"])[0]["documento"] == "INF-AUD-2026-03"


# ---------------------------------------------------------------- búsqueda
def test_tokenizador_conserva_codigos():
    assert "sop-vs-002" in tokenizar("Según el SOP-VS-002 §6.3")
    assert "hplc-qc-03" in tokenizar("equipo HPLC-QC-03")


def test_rrf_caso_de_la_clase():
    # A en los puestos 1 y 3, B en los puestos 2 y 1, k = 60: gana B
    p = rrf([["A", "B"], ["B", "X", "A"]], k=60)
    assert p["B"] == pytest.approx(1 / 62 + 1 / 61)
    assert p["A"] == pytest.approx(1 / 61 + 1 / 63)
    assert p["B"] > p["A"]


def test_buscar_devuelve_el_contrato(buscador):
    r = buscador.buscar("audit trail", "u_analista_qa", k=3)
    assert len(r) == 3
    for f in r:
        assert {"documento", "fragmento_id", "texto", "puntaje", "seccion"} <= f.keys()


# ---------------------------------------------------------------- citas y reglas nuevas
SALIDA_OK = {
    "fuera_de_alcance": False, "impacto_gxp": "mayor", "requiere_revalidacion": True,
    "justificacion": "Afecta un sistema computarizado validado que genera registros electrónicos.",
    "fundamento": [{"codigo": "SOP-VS-002", "seccion": "6.3"}],
    "tareas": [{"descripcion": "Evaluación de riesgo de la nueva versión", "area_responsable": "validaciones"}],
    "confianza": 0.8,
}


def test_fundamento_rechaza_documento_no_recuperado():
    with pytest.raises(ValidationError, match="no está entre las fuentes recuperadas"):
        Salida.model_validate(SALIDA_OK, context={"fuentes": {"SOP-CC-001": {"5.6"}}})


def test_fundamento_rechaza_seccion_no_recuperada():
    with pytest.raises(ValidationError, match="secciones recuperadas"):
        Salida.model_validate(SALIDA_OK, context={"fuentes": {"SOP-VS-002": {"5"}}})
    Salida.model_validate(SALIDA_OK, context={"fuentes": {"SOP-VS-002": {"6", "6.3"}}})


def test_regla_h02_sop_en_tarea_sin_fundamento():
    tareas = [{"descripcion": "Revisar el audit trail según SOP-VS-003", "area_responsable": "validaciones"}]
    with pytest.raises(ValidationError, match="H-02"):
        Salida.model_validate({**SALIDA_OK, "tareas": tareas})


def test_requiere_humano_no_clasifica():
    with pytest.raises(ValidationError, match="sin evidencia no se clasifica"):
        Salida.model_validate({**SALIDA_OK, "requiere_humano": True})
    Salida.model_validate({**SALIDA_OK, "requiere_humano": True, "impacto_gxp": None, "tareas": [],
                           "fundamento": [], "requiere_revalidacion": False})


def test_sin_evidencia_no_llama_al_modelo(buscador, monkeypatch):
    monkeypatch.setitem(CONFIG_RAG, "umbral_similitud", 1.01)
    simulado = ProveedorSimulado("rag_valido")
    r = responder(ENTRADA, "u_analista_qa", simulado, buscador)
    assert r.ok and r.propuesta.requiere_humano and r.propuesta.impacto_gxp is None
    assert simulado.ultimo_prompt == "" and r.metricas is None


def test_modelo_puede_pedir_humano(buscador, sin_umbral):
    r = responder(ENTRADA, "u_analista_qa", ProveedorSimulado("rag_sin_evidencia"), buscador)
    assert r.ok and r.propuesta.requiere_humano and r.propuesta.fundamento == []


def test_responder_cita_solo_lo_recuperado(buscador, sin_umbral):
    r = responder(ENTRADA, "u_analista_qa", ProveedorSimulado("rag_valido"), buscador)
    assert r.ok, r.error
    recuperados = {f.documento for f in r.fuentes}
    assert {c.codigo for c in r.propuesta.fundamento} <= recuperados
    assert r.propuesta.estado == "BORRADOR_PENDIENTE_QA"
    assert r.version_prompt.startswith("rag-")


def test_pregunta_restringida_sin_citas_del_restringido(buscador, sin_umbral):
    simulado = ProveedorSimulado("rag_sin_evidencia")
    r = responder_pregunta("¿Qué hallazgos dejó la inspección regulatoria?", "u_solicitante_prod", simulado, buscador)
    assert r.ok and r.salida.requiere_humano and r.salida.citas == []
    assert "HAL-INSP-2026-01" not in simulado.ultimo_prompt
