"""Pruebas de la corrida única (devolución de la PE2): sin clave ni internet."""
import hashlib
import json

import pytest

from scripts import corrida


@pytest.fixture(scope="module")
def carpeta(tmp_path_factory):
    destino = tmp_path_factory.mktemp("res") / "corrida_prueba"
    return corrida.correr(simulado="valido", destino=destino)


def test_genera_todos_los_archivos(carpeta):
    casos, _ = corrida.casos_a_correr()
    nombres = {f.name for f in carpeta.iterdir()}
    for archivo in casos:
        n = archivo.name[:2]
        assert {f"caso_{n}.txt", f"caso_{n}.json"} <= nombres
    assert {"error_reintento.txt", "error_api.txt", "error_entrada.txt",
            "medicion.md", "medicion.json", "manifiesto.json"} <= nombres


def test_medicion_coincide_con_cada_caso(carpeta):
    """Una sola fuente de verdad: cada fila de la tabla es exactamente su caso_NN.json."""
    med = json.loads((carpeta / "medicion.json").read_text(encoding="utf-8"))
    for fila in med["filas"]:
        r = json.loads((carpeta / f"caso_{fila['n']}.json").read_text(encoding="utf-8"))
        m = r["metricas"]
        assert (fila["tokens_entrada"], fila["tokens_salida"], fila["costo_usd"], fila["latencia_ms"], fila["trace_id"]) == \
               (m["input_tokens"], m["output_tokens"], m["cost"], m["latencia_ms"], r["trace_id"])


def test_terminal_completa_y_mismo_trace(carpeta):
    for txt in carpeta.glob("caso_*.txt"):
        texto = txt.read_text(encoding="utf-8")
        assert texto.startswith("$ python -m src.motor ")
        assert "…" not in texto
        r = json.loads((carpeta / txt.name.replace(".txt", ".json")).read_text(encoding="utf-8"))
        assert r["trace_id"] in texto


def test_manifiesto_con_hashes_correctos(carpeta):
    man = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    assert man["modo"] == "simulado:valido" and man["version_prompt"]
    for nombre, hash_ in man["archivos"].items():
        assert hashlib.sha256((carpeta / nombre).read_bytes()).hexdigest() == hash_


def test_errores_estructurados_en_la_evidencia(carpeta):
    assert "salida_invalida" in (carpeta / "error_reintento.txt").read_text(encoding="utf-8")
    assert "fundamento -> 0 -> codigo" in (carpeta / "error_reintento.txt").read_text(encoding="utf-8")
    assert "api_sin_conexion" in (carpeta / "error_api.txt").read_text(encoding="utf-8")
    assert "entrada_invalida" in (carpeta / "error_entrada.txt").read_text(encoding="utf-8")
    for txt in carpeta.glob("*.txt"):
        assert "Traceback" not in txt.read_text(encoding="utf-8")


def test_casos_sin_clasificar_se_saltean(tmp_path, monkeypatch):
    (tmp_path / "consultas").mkdir()
    (tmp_path / "consultas" / "01_a.json").write_text(json.dumps({"esperado": {"impacto_gxp": "menor"}}))
    (tmp_path / "consultas" / "02_b.json").write_text(json.dumps({"esperado": {"impacto_gxp": "A_CONFIRMAR_POR_QA"}}))
    monkeypatch.setattr(corrida, "RAIZ", tmp_path)
    elegidos, salteados = corrida.casos_a_correr()
    assert [a.name for a in elegidos] == ["01_a.json"] and salteados == ["02_b.json"]


def test_los_diez_casos_nuevos_tienen_criterio_de_qa():
    casos, salteados = corrida.casos_a_correr()
    assert len(casos) >= 15 and not salteados
    for archivo in casos:
        if int(archivo.name[:2]) >= 6:
            esperado = json.loads(archivo.read_text(encoding="utf-8"))["esperado"]
            assert esperado["impacto_gxp"] in {"sin_impacto", "menor", "mayor", "critico"}
            assert esperado["justificacion_qa"] and esperado["clasificado_por"].startswith("Federico")
