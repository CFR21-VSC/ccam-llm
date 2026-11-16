"""Lectura y fragmentado de los documentos del laboratorio (PE3).

QUÉ HACE ESTE ARCHIVO
    1. Lee cada documento de documentos/ con su encabezado (código, título,
       versión, vigencia y roles que lo pueden leer).
    2. Lo corta en secciones numeradas (## 5 ..., ### 5.6 ...).
    3. Arma los fragmentos: junta secciones seguidas hasta el tamaño máximo,
       con ~10 % de solapamiento, y le pone a cada uno un prefijo verificable
       ("SOP-VS-002 · Validación de sistemas computarizados · §6.3 ...").

EQUIVALENTE GxP
    El encabezado es la carátula del documento controlado; el hash SHA-256 es
    la huella que prueba qué versión exacta se indexó (como la versión vigente
    de la lista maestra). El prefijo no inventa nada: sale del propio documento.

TOKENS
    Se estiman como caracteres / 4. Es una aproximación declarada (el
    tokenizador real depende del modelo); alcanza para comparar dos tamaños.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

ROLES = ("solicitante", "analista_qa", "validaciones", "jefe_qa")
_TITULO = re.compile(r"^(#{2,3})\s+(\d+(?:\.\d+)*)\s+(.+?)\s*$")


@dataclass
class Documento:
    codigo: str
    titulo: str
    version: str
    vigente_desde: str
    roles: list[str]
    cuerpo: str
    hash: str
    archivo: str


@dataclass
class Seccion:
    numero: str
    titulo: str
    texto: str          # incluye la línea de título


@dataclass
class Fragmento:
    documento: str
    titulo_documento: str
    secciones: list[str]
    texto: str          # prefijo + contenido: es lo que se indexa y lo que ve el modelo
    chunk_index: int
    fragmento_id: str
    version: str
    hash_documento: str
    roles: list[str] = field(default_factory=list)

    @property
    def seccion(self) -> str:
        return self.secciones[0]

    @property
    def tokens(self) -> int:
        return estimar_tokens(self.texto)

    def metadatos(self) -> dict:
        """Lo que se guarda en ChromaDB junto a cada fragmento (todo escalar, como exige Chroma)."""
        return {
            "documento": self.documento, "titulo": self.titulo_documento, "seccion": self.seccion,
            "secciones": ",".join(self.secciones), "version": self.version,
            "fragmento_id": self.fragmento_id, "chunk_index": self.chunk_index,
            "hash_documento": self.hash_documento, "tokens": self.tokens,
            # un booleano por rol: el filtro de permisos es un where simple
            **{f"rol_{r}": (r in self.roles) for r in ROLES},
        }


def estimar_tokens(texto: str) -> int:
    return math.ceil(len(texto) / 4)


# ------------------------------------------------------------ lectura
def leer_documento(ruta: Path) -> Documento:
    crudo = ruta.read_bytes()
    texto = crudo.decode("utf-8").replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, flags=re.S)
    if not m:
        raise ValueError(f"{ruta.name}: falta el encabezado YAML entre líneas ---")
    cabecera: dict[str, str] = {}
    for linea in m.group(1).splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            cabecera[clave.strip()] = valor.strip()
    faltan = {"codigo", "titulo", "version", "vigente_desde", "roles_lectura"} - cabecera.keys()
    if faltan:
        raise ValueError(f"{ruta.name}: faltan campos en el encabezado: {sorted(faltan)}")
    roles = [r.strip() for r in cabecera["roles_lectura"].split(",") if r.strip()]
    desconocidos = set(roles) - set(ROLES)
    if desconocidos:
        raise ValueError(f"{ruta.name}: roles desconocidos {sorted(desconocidos)}")
    return Documento(codigo=cabecera["codigo"], titulo=cabecera["titulo"], version=cabecera["version"],
                     vigente_desde=cabecera["vigente_desde"], roles=roles, cuerpo=m.group(2).strip(),
                     hash=hashlib.sha256(crudo).hexdigest(), archivo=ruta.name)


def leer_carpeta(carpeta: Path) -> list[Documento]:
    return [leer_documento(p) for p in sorted(Path(carpeta).glob("*.md"))]


def secciones(doc: Documento) -> list[Seccion]:
    """Corta en secciones numeradas. Lo que está antes de la primera (título y nota) va con la primera."""
    resultado: list[Seccion] = []
    preambulo: list[str] = []
    actual: Seccion | None = None
    for linea in doc.cuerpo.splitlines():
        m = _TITULO.match(linea)
        if m:
            if actual:
                resultado.append(actual)
            actual = Seccion(numero=m.group(2), titulo=m.group(3), texto=linea)
            if not resultado and preambulo:  # primera sección: arrastra la nota del documento
                actual.texto = "\n".join(l for l in preambulo if not l.startswith("# ")).strip() + "\n\n" + linea
        elif actual is None:
            preambulo.append(linea)
        else:
            actual.texto += "\n" + linea
    if actual:
        resultado.append(actual)
    for s in resultado:
        s.texto = s.texto.strip()
    return resultado


# ------------------------------------------------------------ fragmentado
def _partir(texto: str, max_chars: int) -> list[str]:
    """Recursivo: primero por párrafo, después por línea, al final por caracteres."""
    if len(texto) <= max_chars:
        return [texto]
    for separador in ("\n\n", "\n"):
        partes = texto.split(separador)
        if len(partes) > 1:
            trozos, actual = [], ""
            for p in partes:
                candidato = f"{actual}{separador}{p}" if actual else p
                if len(candidato) <= max_chars:
                    actual = candidato
                else:
                    if actual:
                        trozos.append(actual)
                    actual = p
            if actual:
                trozos.append(actual)
            return [t for trozo in trozos for t in _partir(trozo, max_chars)]
    return [texto[i:i + max_chars] for i in range(0, len(texto), max_chars)]


def _cola(texto: str, chars: int) -> str:
    """Los últimos ~chars caracteres, empezando en un borde de palabra (para el solapamiento)."""
    if chars <= 0 or len(texto) <= chars:
        return ""
    cola = texto[-chars:]
    espacio = cola.find(" ")
    return cola[espacio + 1:] if espacio >= 0 else cola


def prefijo(doc: Documento, secs: list[Seccion]) -> str:
    """Contextual retrieval sin inventar: código, título y secciones, tal como figuran en el documento."""
    primera = f"§{secs[0].numero} {secs[0].titulo}"
    rango = f" a §{secs[-1].numero} {secs[-1].titulo}" if len(secs) > 1 else ""
    return f"{doc.codigo} · {doc.titulo} · {primera}{rango}"


def fragmentar(doc: Documento, max_tokens: int, solapamiento: float = 0.10, etiqueta: str = "A") -> list[Fragmento]:
    """Junta secciones seguidas mientras entren en max_tokens; si una sola no entra, la parte."""
    # el tope incluye el prefijo (~120 caracteres) y el solapamiento: el contenido propio entra en lo que queda
    max_chars = int(max_tokens * 4 * (1 - solapamiento)) - 120
    unidades: list[tuple[Seccion, str]] = []
    for s in secciones(doc):
        for trozo in _partir(s.texto, max_chars):
            unidades.append((s, trozo))

    grupos: list[list[tuple[Seccion, str]]] = []
    actual: list[tuple[Seccion, str]] = []
    largo = 0
    for u in unidades:
        if actual and largo + len(u[1]) + 2 > max_chars:
            grupos.append(actual)
            actual, largo = [], 0
        actual.append(u)
        largo += len(u[1]) + 2
    if actual:
        grupos.append(actual)

    fragmentos: list[Fragmento] = []
    anterior = ""
    for i, grupo in enumerate(grupos):
        secs: list[Seccion] = []
        for s, _ in grupo:
            if s not in secs:
                secs.append(s)
        contenido = "\n\n".join(t for _, t in grupo)
        solape = _cola(anterior, int(len(anterior) * solapamiento))
        cuerpo = (f"[…] {solape}\n\n" if solape else "") + contenido
        fragmentos.append(Fragmento(
            documento=doc.codigo, titulo_documento=doc.titulo, secciones=[s.numero for s in secs],
            texto=prefijo(doc, secs) + "\n\n" + cuerpo, chunk_index=i,
            fragmento_id=f"{doc.codigo}#{etiqueta}{i:02d}", version=doc.version,
            hash_documento=doc.hash, roles=list(doc.roles)))
        anterior = contenido
    return fragmentos
