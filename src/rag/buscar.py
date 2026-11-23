"""Búsqueda híbrida con permisos: vectorial + BM25, fusionadas con RRF.

EL RECORRIDO DE UNA BÚSQUEDA (función buscar)
    1. Resuelve quién pregunta con config/usuarios.json (el código, nunca el modelo).
       Usuario desconocido -> lista vacía y registro "acceso_denegado".
    2. PRE-FILTRO: la consulta a ChromaDB lleva where={"rol_<rol>": True}.
       Lo que el rol no puede leer no se busca: no "se busca y después se oculta".
    3. BM25 (coincidencia de palabras exactas) se arma SOLO con los fragmentos
       autorizados. Si se armara con todo el corpus, los puntajes delatarían
       que existe un documento restringido sobre el tema.
    4. Fusión RRF: puntaje = suma de 1 / (60 + puesto) en cada ranking.
    5. Devuelve los k mejores con documento, sección, fragmento_id, texto y puntaje.

EQUIVALENTE GxP
    Es el control de accesos por perfil del sistema documental: el archivo
    restringido no aparece en el listado de quien no tiene el perfil.
    Segregación de funciones aplicada a la lectura.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.rag.embeddings import EmbedderSimulado, crear_embedder
from src.rag.ingestar import CONFIG_RAG, _cliente, nombre_coleccion, ruta_base

RAIZ = Path(__file__).resolve().parent.parent.parent
ARCHIVO_LOG = RAIZ / "logs" / "busquedas.jsonl"
USUARIOS = json.loads((RAIZ / "config" / "usuarios.json").read_text(encoding="utf-8"))

_STOP = set("""a al ante con de del desde el en entre es la las lo los o para por que se si sin sobre su sus un una
uno unos y e u le les me mi como cual cuales cuando hay qué cuál cómo pide dice esta este esto""".split())


# ------------------------------------------------------------ identidad
def roles_de(usuario: str) -> list[str]:
    datos = USUARIOS["usuarios"].get(usuario)
    if not datos:
        return []
    rol = datos["rol"]
    return [rol] if rol in USUARIOS["roles"] else []


def filtro_roles(roles: list[str]) -> dict:
    """El where de ChromaDB. Con un rol: {"rol_x": True}; con varios, un $or."""
    condiciones = [{f"rol_{r}": True} for r in roles]
    return condiciones[0] if len(condiciones) == 1 else {"$or": condiciones}


# ------------------------------------------------------------ BM25
RAIZ_LARGO = 6  # "desactivar", "desactivarlo" y "desactiva" cuentan como el mismo término: "desact"


def tokenizar(texto: str) -> list[str]:
    """Minúsculas, sin tildes, y los códigos con guiones quedan enteros: 'sop-vs-002' es UN término.

    Las palabras comunes se recortan a sus primeras 6 letras (raíz aproximada, sin diccionario):
    así una conjugación distinta no deja de coincidir. Los códigos y números no se recortan nunca.
    """
    plano = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    terminos = []
    for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", plano):
        if t in _STOP:
            continue
        es_codigo = "-" in t or any(c.isdigit() for c in t)
        terminos.append(t if es_codigo else t[:RAIZ_LARGO])
    return terminos


# ------------------------------------------------------------ fusión
def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion. rankings = listas de ids, del mejor al peor (puesto 1 = primero)."""
    puntajes: dict[str, float] = {}
    for ranking in rankings:
        for puesto, fid in enumerate(ranking, start=1):
            puntajes[fid] = puntajes.get(fid, 0.0) + 1.0 / (k + puesto)
    return puntajes


# ------------------------------------------------------------ el buscador
class Buscador:
    """Una colección de ChromaDB abierta, con su embedder. Se usa para buscar muchas veces."""

    def __init__(self, config: Optional[str] = None, destino: Optional[Path] = None, coleccion=None, embedder=None):
        self.config = config or CONFIG_RAG["configuracion_vigente"]
        if coleccion is None:
            base = destino or ruta_base(self.config)
            if not base.exists():
                raise FileNotFoundError(f"No hay base en {base}: correr antes python -m src.rag.ingestar")
            coleccion = _cliente(base).get_collection(nombre_coleccion(self.config), embedding_function=None)
        self.coleccion = coleccion
        if embedder is None:  # siempre el mismo embedder con el que se ingestó
            usado = (coleccion.metadata or {}).get("modelo_embeddings", "")
            embedder = EmbedderSimulado() if usado == EmbedderSimulado.nombre else crear_embedder(False)
        self.embedder = embedder

    # -- piezas sueltas (la medición las compara con la híbrida)
    def _autorizados(self, roles: list[str]) -> dict:
        return self.coleccion.get(where=filtro_roles(roles), include=["documents", "metadatas"])

    def buscar_vectorial(self, consulta: str, roles: list[str], n: Optional[int] = None) -> list[dict]:
        if not roles:
            return []
        total = len(self._autorizados(roles)["ids"])
        if total == 0:
            return []
        r = self.coleccion.query(query_embeddings=self.embedder([consulta]), n_results=min(n or total, total),
                                 where=filtro_roles(roles), include=["documents", "metadatas", "distances"])
        return [_fragmento(fid, doc, meta, similitud=round(1 - dist, 4))
                for fid, doc, meta, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])]

    def buscar_bm25(self, consulta: str, roles: list[str], n: Optional[int] = None) -> list[dict]:
        from rank_bm25 import BM25Okapi

        if not roles:
            return []
        base = self._autorizados(roles)  # SOLO lo autorizado entra al índice léxico
        if not base["ids"]:
            return []
        indice = BM25Okapi([tokenizar(t) for t in base["documents"]])
        puntajes = indice.get_scores(tokenizar(consulta))
        orden = sorted(range(len(puntajes)), key=lambda i: (-puntajes[i], base["ids"][i]))
        return [_fragmento(base["ids"][i], base["documents"][i], base["metadatas"][i], bm25=round(float(puntajes[i]), 4))
                for i in orden[: n or len(orden)] if puntajes[i] > 0]

    def buscar(self, consulta: str, usuario: str, k: Optional[int] = None) -> list[dict]:
        k = k or CONFIG_RAG["k"]
        roles = roles_de(usuario)
        if not roles:
            _registrar(usuario, None, consulta, "acceso_denegado", [])
            return []
        vectorial = self.buscar_vectorial(consulta, roles)
        lexica = self.buscar_bm25(consulta, roles)
        fusion = rrf([[f["fragmento_id"] for f in vectorial], [f["fragmento_id"] for f in lexica]],
                     CONFIG_RAG["rrf_k"])
        por_id = {f["fragmento_id"]: f for f in vectorial}
        for f in lexica:
            por_id.setdefault(f["fragmento_id"], f).update(bm25=f["bm25"])
        orden = sorted(fusion, key=lambda fid: (-fusion[fid], fid))[:k]
        resultado = [{**por_id[fid], "puntaje": round(fusion[fid], 6)} for fid in orden]
        _registrar(usuario, roles, consulta, "ok", [f["fragmento_id"] for f in resultado])
        return resultado


def _fragmento(fid: str, texto: str, meta: dict, **extra) -> dict:
    return {"documento": meta["documento"], "seccion": meta["seccion"], "secciones": meta["secciones"].split(","),
            "version": meta.get("version"), "hash_documento": meta.get("hash_documento"),
            "fragmento_id": fid, "texto": texto, **extra}


def _registrar(usuario: str, roles, consulta: str, evento: str, ids: list[str]) -> None:
    """Rastro de cada búsqueda. La consulta va como hash: el texto del CCAM no queda en el log."""
    ARCHIVO_LOG.parent.mkdir(exist_ok=True)
    with ARCHIVO_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "usuario": usuario, "roles": roles, "evento": evento,
            "consulta_sha256": hashlib.sha256(consulta.encode("utf-8")).hexdigest()[:16],
            "fragmentos": ids}, ensure_ascii=False) + "\n")


# ------------------------------------------------------------ contrato de la consigna
_POR_DEFECTO: dict[str, Buscador] = {}


def buscar(consulta: str, usuario: str, k: Optional[int] = None, buscador: Optional[Buscador] = None) -> list[dict]:
    """buscar(consulta, usuario, k) -> [{documento, fragmento_id, texto, puntaje, seccion, ...}]"""
    if buscador is None:
        config = CONFIG_RAG["configuracion_vigente"]
        buscador = _POR_DEFECTO.setdefault(config, Buscador(config))
    return buscador.buscar(consulta, usuario, k)
