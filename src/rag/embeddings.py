"""Embeddings: convierten un texto en una lista de números que representa su significado.

QUÉ HACE ESTE ARCHIVO
    - EmbedderLocal: modelo multilingüe que corre en la máquina, gratis y sin
      mandar los documentos a ningún tercero (fastembed + ONNX).
      Modelo: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2,
      licencia Apache-2.0, 384 dimensiones, ~220 MB. Se baja una sola vez.
    - EmbedderSimulado: determinístico, sin descargas. Lo usan las pruebas y
      la CI. No mide calidad de búsqueda: solo permite probar permisos,
      metadatos y el armado del prompt sin internet.

EQUIVALENTE GxP
    El modelo de embeddings es un componente más del sistema: su nombre queda
    en el manifiesto de la ingesta, igual que la versión de un software en el
    inventario de sistemas.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from pathlib import Path

MODELO_LOCAL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RAIZ = Path(__file__).resolve().parent.parent.parent


class EmbedderLocal:
    def __init__(self, modelo: str = MODELO_LOCAL):
        from fastembed import TextEmbedding  # se importa acá: las pruebas no lo necesitan

        cache = os.getenv("FASTEMBED_CACHE_PATH", str(RAIZ / ".cache" / "fastembed"))
        self.nombre = f"{modelo} (ventanas de {self.VENTANA_CHARS} caracteres, promedio)"
        self._modelo = TextEmbedding(model_name=modelo, cache_dir=cache)

    # El modelo solo "lee" los primeros 128 tokens de cada texto (lo demás lo corta sin avisar).
    # Un fragmento de ~400 tokens quedaría representado solo por su comienzo. Por eso cada
    # fragmento largo se parte en ventanas de ~350 caracteres (cada una con el prefijo del
    # fragmento), se calcula un vector por ventana y se promedian (hallazgo H-17).
    VENTANA_CHARS = 350

    def _ventanas(self, texto: str) -> list[str]:
        if len(texto) <= self.VENTANA_CHARS:
            return [texto]
        cabeza, _, cuerpo = texto.partition("\n")
        partes = [p for p in re.split(r"(?<=[.:;])\s+|\n+", cuerpo) if p.strip()]
        ventanas, actual = [], ""
        for parte in partes:
            if actual and len(actual) + len(parte) > self.VENTANA_CHARS:
                ventanas.append(actual)
                actual = ""
            actual = f"{actual} {parte}".strip()
        if actual:
            ventanas.append(actual)
        return [f"{cabeza}\n{v}" for v in ventanas] or [texto]

    def __call__(self, textos: list[str]) -> list[list[float]]:
        vectores = []
        for texto in textos:
            partes = list(self._modelo.embed(self._ventanas(texto)))
            media = [float(sum(v[i] for v in partes)) / len(partes) for i in range(len(partes[0]))]
            norma = math.sqrt(sum(x * x for x in media)) or 1.0
            vectores.append([x / norma for x in media])
        return vectores


class EmbedderSimulado:
    """Bolsa de palabras con 'hashing': cada palabra suma en una posición fija del vector."""

    nombre = "simulado-hash-384"
    DIM = 384

    def __call__(self, textos: list[str]) -> list[list[float]]:
        vectores = []
        for t in textos:
            v = [0.0] * self.DIM
            plano = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
            for palabra in re.findall(r"[a-z0-9]+", plano):
                h = int(hashlib.md5(palabra.encode()).hexdigest(), 16)
                v[h % self.DIM] += 1.0
            norma = math.sqrt(sum(x * x for x in v)) or 1.0
            vectores.append([x / norma for x in v])
        return vectores


def crear_embedder(simulado: bool | None = None):
    """simulado=None: decide la variable RAG_EMBEDDINGS (local | simulado). Por defecto, local."""
    if simulado is None:
        simulado = os.getenv("RAG_EMBEDDINGS", "local").strip().lower() == "simulado"
    return EmbedderSimulado() if simulado else EmbedderLocal()
