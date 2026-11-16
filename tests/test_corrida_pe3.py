"""La corrida de la PE3 completa, sin clave ni descargas (embeddings y modelo simulados)."""
import hashlib
import json

from scripts.corrida_pe3 import correr


def test_corrida_pe3_simulada_deja_evidencia_completa(tmp_path):
    carpeta = correr("rag_valido", embeddings_simulados=True, pausa=0, destino=tmp_path / "corrida_pe3")
    for nombre in ("recuperacion.json", "permisos.json", "medicion.json", "medicion.md", "manifiesto.json",
                   "ingesta_A.json", "ingesta_B.json"):
        assert (carpeta / nombre).exists(), nombre
    assert len(list((carpeta / "preguntas").glob("P*.json"))) == 10
    assert len(list((carpeta / "ccam").glob("caso_*.json"))) == 15

    permisos = json.loads((carpeta / "permisos.json").read_text(encoding="utf-8"))
    assert permisos["testigos_correctos"] == "12/12"
    assert permisos["usuario_desconocido_recibe"] == 0

    manifiesto = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    assert manifiesto["modo"] == "simulado:rag_valido"
    for nombre, huella in manifiesto["archivos"].items():
        assert hashlib.sha256((carpeta / nombre).read_bytes()).hexdigest() == huella
