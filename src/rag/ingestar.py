"""Ingesta: un solo comando lee documentos/, fragmenta, calcula embeddings y guarda en ChromaDB.

USO
    python -m src.rag.ingestar                 # configuración vigente (config/rag.json)
    python -m src.rag.ingestar --config B      # otra configuración de fragmentado
    python -m src.rag.ingestar --simulado      # embeddings simulados (sin descargar el modelo)

QUÉ DEJA
    .chroma/<config>/                      la base vectorial (no va al repo: se regenera)
    resultados/ingesta/manifiesto_<config>.json
                                           fragmentos por documento, configuración,
                                           modelo de embeddings y hash SHA-256 de cada fuente

EQUIVALENTE GxP
    Es la "carga controlada" de la lista maestra al sistema: cada vez se vuelve
    a cargar todo desde los documentos fuente, y el manifiesto es el registro
    de qué versión exacta de cada documento quedó indexada.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.rag.corpus import Fragmento, fragmentar, leer_carpeta
from src.rag.embeddings import crear_embedder

RAIZ = Path(__file__).resolve().parent.parent.parent
CONFIG_RAG = json.loads((RAIZ / "config" / "rag.json").read_text(encoding="utf-8"))


def _cliente(destino: Path):
    import chromadb
    from chromadb.config import Settings

    destino.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(destino), settings=Settings(anonymized_telemetry=False))


def ruta_base(config: str) -> Path:
    return RAIZ / ".chroma" / config


def nombre_coleccion(config: str) -> str:
    return f"corpus_{config}"


def fragmentos_de(carpeta: Path, config: str) -> list[Fragmento]:
    parametros = CONFIG_RAG["configuraciones"][config]
    return [f for doc in leer_carpeta(carpeta)
            for f in fragmentar(doc, parametros["max_tokens"], parametros["solapamiento"], etiqueta=config)]


def ingestar(carpeta: Path | str = RAIZ / "documentos", config: str | None = None,
             destino: Path | None = None, embedder=None, manifiesto: Path | None = None):
    """Procesa la carpeta completa y devuelve la colección de ChromaDB (se recrea desde cero)."""
    carpeta = Path(carpeta)
    config = config or CONFIG_RAG["configuracion_vigente"]
    destino = destino or ruta_base(config)
    embedder = embedder or crear_embedder()

    documentos = leer_carpeta(carpeta)
    fragmentos = fragmentos_de(carpeta, config)
    cliente = _cliente(destino)
    nombre = nombre_coleccion(config)
    if nombre in [c.name for c in cliente.list_collections()]:
        cliente.delete_collection(nombre)
    coleccion = cliente.create_collection(
        nombre, embedding_function=None,
        metadata={"hnsw:space": "cosine", "modelo_embeddings": embedder.nombre, "config": config})
    coleccion.add(ids=[f.fragmento_id for f in fragmentos],
                  documents=[f.texto for f in fragmentos],
                  metadatas=[f.metadatos() for f in fragmentos],
                  embeddings=embedder([f.texto for f in fragmentos]))

    if manifiesto:
        manifiesto.parent.mkdir(parents=True, exist_ok=True)
        datos = {
            "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "configuracion": config, **CONFIG_RAG["configuraciones"][config],
            "modelo_embeddings": embedder.nombre, "total_fragmentos": len(fragmentos),
            "documentos": [{
                "codigo": d.codigo, "archivo": d.archivo, "version": d.version, "roles_lectura": d.roles,
                "sha256": d.hash,
                "fragmentos": sum(1 for f in fragmentos if f.documento == d.codigo),
                "tokens_por_fragmento": [f.tokens for f in fragmentos if f.documento == d.codigo],
            } for d in documentos],
        }
        manifiesto.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return coleccion


def main() -> int:
    p = argparse.ArgumentParser(description="Ingesta de documentos/ en ChromaDB.")
    p.add_argument("--config", choices=sorted(CONFIG_RAG["configuraciones"]), default=None)
    p.add_argument("--carpeta", default=str(RAIZ / "documentos"))
    p.add_argument("--simulado", action="store_true", help="embeddings simulados (pruebas, sin descarga)")
    a = p.parse_args()
    config = a.config or CONFIG_RAG["configuracion_vigente"]
    salida = RAIZ / "resultados" / "ingesta" / f"manifiesto_{config}.json"
    col = ingestar(a.carpeta, config, embedder=crear_embedder(True if a.simulado else None), manifiesto=salida)
    print(f"Ingesta {config}: {col.count()} fragmentos en {ruta_base(config).relative_to(RAIZ)} "
          f"| manifiesto {salida.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
