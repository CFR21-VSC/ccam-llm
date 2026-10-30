"""Pruebas sin gastar tokens: el contrato y el motor con el proveedor simulado.

Correr con:  python -m pytest -q
"""
import pytest
from pydantic import ValidationError

from src.contrato import Entrada, Salida
from src.motor import evaluar
from src.proveedores import ProveedorSimulado

ENTRADA_OK = {
    "id_ccam": "CCAM-2026-101", "tipo_cambio": "version_software", "area_solicitante": "control_calidad",
    "sistema_afectado": "Software cromatográfico",
    "descripcion": "Actualizar el software cromatográfico de la versión 3.6 a la 3.8 por fin de soporte.",
}
SALIDA_OK = {
    "fuera_de_alcance": False, "impacto_gxp": "mayor", "requiere_revalidacion": True,
    "justificacion": "Afecta un sistema computarizado validado que genera registros electrónicos.",
    "fundamento": [{"codigo": "SOP-VS-002", "seccion": "6.3"}],
    "tareas": [{"descripcion": "Evaluación de riesgo de la nueva versión", "area_responsable": "validaciones"}],
    "confianza": 0.8,
}


def campos(exc):
    return {".".join(map(str, e["loc"])) for e in exc.value.errors()}


# ---- Prueba A: lo correcto pasa
def test_entrada_y_salida_validas():
    Entrada.model_validate(ENTRADA_OK)
    assert Salida.model_validate(SALIDA_OK).estado == "BORRADOR_PENDIENTE_QA"


# ---- Prueba B: reglas de campo (patrón, Enum, largo mínimo)
def test_entrada_invalida_dice_que_campos_fallan():
    with pytest.raises(ValidationError) as exc:
        Entrada.model_validate({**ENTRADA_OK, "id_ccam": "2026-1", "tipo_cambio": "urgente", "descripcion": "corto"})
    assert {"id_ccam", "tipo_cambio", "descripcion"} <= campos(exc)


def test_confianza_fuera_de_rango():
    with pytest.raises(ValidationError) as exc:
        Salida.model_validate({**SALIDA_OK, "confianza": -0.2})
    assert "confianza" in campos(exc)


def test_sop_inexistente_rechazado():
    with pytest.raises(ValidationError) as exc:
        Salida.model_validate({**SALIDA_OK, "fundamento": [{"codigo": "SOP-QA-099", "seccion": "1"}]})
    assert "fundamento.0.codigo" in campos(exc)


def test_estado_no_puede_ser_aprobado():
    with pytest.raises(ValidationError):
        Salida.model_validate({**SALIDA_OK, "estado": "APROBADO"})


# ---- Prueba C: reglas cruzadas
def test_impacto_mayor_sin_tareas():
    with pytest.raises(ValidationError, match="al menos una tarea"):
        Salida.model_validate({**SALIDA_OK, "tareas": []})


def test_dentro_de_alcance_sin_fundamento():
    with pytest.raises(ValidationError, match="al menos un SOP"):
        Salida.model_validate({**SALIDA_OK, "fundamento": []})


def test_revalidacion_con_sin_impacto():
    with pytest.raises(ValidationError, match="incompatible"):
        Salida.model_validate({**SALIDA_OK, "impacto_gxp": "sin_impacto"})


def test_fuera_de_alcance_coherente():
    Salida.model_validate({**SALIDA_OK, "fuera_de_alcance": True, "impacto_gxp": None, "requiere_revalidacion": False,
                           "tareas": [], "fundamento": [],
                           "justificacion": "La consulta es administrativa y no corresponde a un cambio GxP."})


# ---- Motor completo con el simulado
def test_motor_valido():
    r = evaluar(ENTRADA_OK, ProveedorSimulado("valido"))
    assert r.ok and r.metricas.intentos == 1


def test_motor_reintenta_y_corrige():
    r = evaluar(ENTRADA_OK, ProveedorSimulado("invalido_luego_valido"))
    assert r.ok and r.metricas.intentos == 2


def test_motor_error_estructurado_tras_reintento():
    r = evaluar(ENTRADA_OK, ProveedorSimulado("invalido"))
    assert not r.ok and r.error.error == "salida_invalida" and r.error.intentos == 2
    assert any(c["campo"] == "fundamento -> 0 -> codigo" for c in r.error.campos)


def test_motor_entrada_invalida_no_llama_al_modelo():
    r = evaluar({**ENTRADA_OK, "id_ccam": "x"}, ProveedorSimulado("sin_conexion"))
    assert r.error.error == "entrada_invalida" and r.metricas is None


def test_sin_clave_da_error_estructurado(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = evaluar(ENTRADA_OK)
    assert not r.ok and r.error.error == "api_autenticacion"


@pytest.mark.parametrize("escenario,tipo", [("sin_conexion", "api_sin_conexion"), ("limite_uso", "api_limite_uso")])
def test_motor_errores_de_api(escenario, tipo):
    r = evaluar(ENTRADA_OK, ProveedorSimulado(escenario))
    assert not r.ok and r.error.error == tipo
