"""Respuesta con fuentes: el motor de la PE2, ahora con los documentos del laboratorio.

EL RECORRIDO DE UN CCAM (función responder)
    1. Valida la Entrada (mismo contrato de la PE2).
    2. Resuelve el usuario. Desconocido -> error "acceso_denegado", sin buscar ni llamar al modelo.
    3. Busca con los permisos de ESE usuario dos veces:
         a) con el CCAM (tipo de cambio, sistema y descripción);
         b) la matriz de clasificación de SOP-CC-001 (es el criterio, se trae siempre).
    4. Sin evidencia (ningún fragmento del CCAM supera el umbral de config/rag.json):
       requiere_humano=true sin llamar al modelo (costo cero).
    5. Arma el prompt con los fragmentos (prompts/sistema_rag.md) en lugar del catálogo cerrado.
    6. Llama, valida y reintenta igual que la PE2. El validador exige que cada cita
       esté entre los fragmentos recuperados en ESTA llamada (contexto "fuentes").
    7. Deja rastro en logs/ejecuciones.jsonl con usuario, rol y fragmentos usados, sin el texto del CCAM.

EQUIVALENTE GxP
    Es la evaluación de impacto hecha "con el procedimiento abierto sobre la mesa":
    todo lo que se afirma se puede rastrear a un documento, sección y versión.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.contrato import Entrada, ErrorEstructurado, ReferenciaSOP, Salida
from src.motor import ARCHIVO_LOG, Metricas, campos_fallidos, herramienta_salida, llamar_con_reintento
from src.proveedores import ErrorProveedor, Proveedor, ProveedorSimulado, crear_proveedor
from src.rag.buscar import Buscador, roles_de
from src.rag.ingestar import CONFIG_RAG

RAIZ = Path(__file__).resolve().parent.parent.parent
DIR_PROMPTS = RAIZ / "prompts"


# ------------------------------------------------------------ contrato de la respuesta
class Fuente(BaseModel):
    """Un fragmento que el sistema RECUPERÓ y le mostró al modelo (no es lo mismo que una cita).

    fundamento (en la Salida) = lo que el modelo CITA; fuentes = lo que se le dio para leer.
    Toda cita del fundamento tiene que estar entre las fuentes; no toda fuente termina citada.
    """
    documento: str
    seccion: str
    secciones: list[str] = Field(default_factory=list)   # todas las secciones que cubre el fragmento
    version: Optional[str] = None                        # versión vigente del documento indexado
    hash_documento: Optional[str] = None                 # SHA-256 del archivo fuente: prueba qué texto exacto se usó
    fragmento_id: str
    puntaje: float                                       # RRF de la búsqueda híbrida
    similitud: Optional[float] = None                    # coseno de la búsqueda vectorial (0 a 1)


class RespuestaRAG(BaseModel):
    """Lo que entrega responder(): la Salida de la PE2 más las fuentes que la respaldan."""
    trace_id: str
    ok: bool
    usuario: str
    propuesta: Optional[Salida] = None
    fuentes: list[Fuente] = Field(default_factory=list)
    error: Optional[ErrorEstructurado] = None
    metricas: Optional[Metricas] = None
    version_prompt: str
    evidencia_maxima: Optional[float] = None   # mejor similitud del CCAM contra lo autorizado
    rol: Optional[str] = None                  # el rol con el que se filtró la búsqueda
    configuracion_fragmentos: Optional[str] = None
    modelo_embeddings: Optional[str] = None
    timestamp_utc: Optional[str] = None


class SalidaPregunta(BaseModel):
    """Respuesta a una pregunta libre sobre los documentos (para las 10 preguntas de prueba)."""
    model_config = ConfigDict(extra="forbid")

    respuesta: str = Field(..., min_length=10, max_length=1500)
    citas: list[ReferenciaSOP] = Field(default_factory=list, max_length=6)
    requiere_humano: bool

    @model_validator(mode="after")
    def coherencia(self) -> "SalidaPregunta":
        if not self.requiere_humano and not self.citas:
            raise ValueError("una respuesta con evidencia tiene que citar al menos un documento")
        if self.requiere_humano and self.citas:
            raise ValueError("requiere_humano=true no lleva citas: no hay evidencia que citar")
        return self


class RespuestaPregunta(BaseModel):
    trace_id: str
    ok: bool
    usuario: str
    pregunta_id: Optional[str] = None
    salida: Optional[SalidaPregunta] = None
    fuentes: list[Fuente] = Field(default_factory=list)
    error: Optional[ErrorEstructurado] = None
    metricas: Optional[Metricas] = None
    version_prompt: str
    evidencia_maxima: Optional[float] = None


# ------------------------------------------------------------ piezas
def version_prompt_rag() -> str:
    """Huella de las plantillas del modo RAG + parámetros de búsqueda. Cambia una coma, cambia la versión."""
    h = hashlib.sha256()
    for archivo in ("sistema_rag.md", "pregunta_rag.md", "usuario.md", "correccion.md"):
        h.update((DIR_PROMPTS / archivo).read_bytes())
    h.update((RAIZ / "config" / "rag.json").read_bytes())
    return "rag-" + h.hexdigest()[:12]


def consulta_de(entrada: Entrada) -> str:
    return f"{entrada.tipo_cambio.value.replace('_', ' ')}. {entrada.sistema_afectado}. {entrada.descripcion}"


def unir(*listas: list[dict]) -> list[dict]:
    """Junta resultados de varias búsquedas sin repetir fragmentos (queda el primero que apareció)."""
    vistos, salida = set(), []
    for lista in listas:
        for f in lista:
            if f["fragmento_id"] not in vistos:
                vistos.add(f["fragmento_id"])
                salida.append(f)
    return salida


def formatear_evidencia(fragmentos: list[dict]) -> str:
    return "\n\n".join(f"[F{i}] {f['documento']} §{f['seccion']} (fragmento {f['fragmento_id']})\n{f['texto']}"
                       for i, f in enumerate(fragmentos, start=1))


def contexto_fuentes(fragmentos: list[dict]) -> dict:
    """{codigo: {secciones}} de lo recuperado: es lo único que el validador acepta como cita."""
    fuentes: dict[str, set[str]] = {}
    for f in fragmentos:
        fuentes.setdefault(f["documento"], set()).update(f["secciones"])
    return {"fuentes": fuentes}


def _fuentes(fragmentos: list[dict]) -> list[Fuente]:
    return [Fuente(documento=f["documento"], seccion=f["seccion"], secciones=f.get("secciones", []),
                   version=f.get("version"), hash_documento=f.get("hash_documento"),
                   fragmento_id=f["fragmento_id"], puntaje=f["puntaje"], similitud=f.get("similitud"))
            for f in fragmentos]


def _evidencia_maxima(fragmentos: list[dict]) -> Optional[float]:
    valores = [f.get("similitud") for f in fragmentos if f.get("similitud") is not None]
    return max(valores) if valores else None


def _plantilla(nombre: str) -> Template:
    return Template((DIR_PROMPTS / nombre).read_text(encoding="utf-8"))


_BUSCADOR: dict[str, Buscador] = {}


def _buscador(buscador: Optional[Buscador]) -> Buscador:
    if buscador is not None:
        return buscador
    config = CONFIG_RAG["configuracion_vigente"]
    return _BUSCADOR.setdefault(config, Buscador(config))


# ------------------------------------------------------------ responder (CCAM)
def responder(entrada: dict | Entrada, usuario: str = "u_analista_qa", proveedor: Optional[Proveedor] = None,
              buscador: Optional[Buscador] = None) -> RespuestaRAG:
    trace_id = uuid.uuid4().hex[:12]
    version = version_prompt_rag()
    datos = entrada.model_dump(mode="json") if isinstance(entrada, Entrada) else entrada

    def cerrar(r: RespuestaRAG) -> RespuestaRAG:
        roles = roles_de(usuario)
        r.rol = roles[0] if roles else None
        r.timestamp_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
        usado = buscador or _BUSCADOR.get(CONFIG_RAG["configuracion_vigente"])
        if usado is not None:
            r.configuracion_fragmentos = usado.config
            r.modelo_embeddings = getattr(usado.embedder, "nombre", None)
        return _registrar(r, datos.get("id_ccam") if isinstance(datos, dict) else None,
                          r.propuesta.impacto_gxp.value if r.propuesta and r.propuesta.impacto_gxp else None,
                          r.propuesta.requiere_humano if r.propuesta else None)

    # 1. Entrada
    try:
        entrada = Entrada.model_validate(datos)
    except ValidationError as exc:
        return cerrar(RespuestaRAG(trace_id=trace_id, ok=False, usuario=usuario, version_prompt=version,
                                   error=ErrorEstructurado(error="entrada_invalida", campos=campos_fallidos(exc),
                                                           mensaje="El pedido no cumple el contrato de Entrada.",
                                                           accion="Corregir el pedido y volver a enviarlo")))
    # 2. Identidad (la resuelve el código)
    if not roles_de(usuario):
        return cerrar(RespuestaRAG(trace_id=trace_id, ok=False, usuario=usuario, version_prompt=version,
                                   error=ErrorEstructurado(error="acceso_denegado",
                                                           mensaje="Usuario desconocido: no se busca ni se responde.",
                                                           accion="Verificar el usuario en config/usuarios.json")))
    # 3. Recuperación con permisos
    try:
        b = _buscador(buscador)
    except FileNotFoundError as exc:
        return cerrar(RespuestaRAG(trace_id=trace_id, ok=False, usuario=usuario, version_prompt=version,
                                   error=ErrorEstructurado(error="sin_base_documental", mensaje=str(exc),
                                                           accion="Correr python -m src.rag.ingestar")))
    del_caso = b.buscar(consulta_de(entrada), usuario, CONFIG_RAG["k"])
    matriz = b.buscar(CONFIG_RAG["consulta_matriz"], usuario, CONFIG_RAG["k_matriz"])
    fragmentos = unir(del_caso, matriz)
    maxima = _evidencia_maxima(del_caso)

    # 4. Sin evidencia: no se llama al modelo
    if maxima is None or maxima < CONFIG_RAG["umbral_similitud"]:
        salida = Salida(fuera_de_alcance=False, requiere_humano=True, impacto_gxp=None, requiere_revalidacion=False,
                        confianza=0.0, justificacion=(
                            "Ningún documento autorizado para este usuario supera el umbral de evidencia "
                            f"({CONFIG_RAG['umbral_similitud']}): no se clasifica y se deriva a QA."))
        return cerrar(RespuestaRAG(trace_id=trace_id, ok=True, usuario=usuario, propuesta=salida,
                                   fuentes=_fuentes(del_caso), version_prompt=version, evidencia_maxima=maxima))

    # 5. Prompt con la evidencia
    sistema = _plantilla("sistema_rag.md").substitute(evidencia=formatear_evidencia(fragmentos))
    usuario_txt = _plantilla("usuario.md").substitute(
        id_ccam=entrada.id_ccam, tipo_cambio=entrada.tipo_cambio.value,
        area_solicitante=entrada.area_solicitante.value,
        sistema_afectado=entrada.sistema_afectado, descripcion=entrada.descripcion)

    # 6. Llamada, validación contra las fuentes y reintento
    try:
        proveedor = proveedor or crear_proveedor()
    except ErrorProveedor as exc:
        return cerrar(RespuestaRAG(trace_id=trace_id, ok=False, usuario=usuario, version_prompt=version,
                                   error=ErrorEstructurado(error=exc.tipo, mensaje=exc.mensaje)))
    propuesta, error, metricas = llamar_con_reintento(proveedor, sistema, usuario_txt, herramienta_salida(),
                                                      Salida, contexto=contexto_fuentes(fragmentos),
                                                      trace_id=trace_id)
    return cerrar(RespuestaRAG(trace_id=trace_id, ok=propuesta is not None, usuario=usuario, propuesta=propuesta,
                               fuentes=_fuentes(fragmentos), error=error, metricas=metricas,
                               version_prompt=version, evidencia_maxima=maxima))


# ------------------------------------------------------------ responder_pregunta (las 10 preguntas)
def responder_pregunta(pregunta: str, usuario: str, proveedor: Optional[Proveedor] = None,
                       buscador: Optional[Buscador] = None, pregunta_id: Optional[str] = None) -> RespuestaPregunta:
    trace_id = uuid.uuid4().hex[:12]
    version = version_prompt_rag()

    def cerrar(r: RespuestaPregunta) -> RespuestaPregunta:
        return _registrar(r, pregunta_id, None, r.salida.requiere_humano if r.salida else None)

    if not roles_de(usuario):
        return cerrar(RespuestaPregunta(trace_id=trace_id, ok=False, usuario=usuario, pregunta_id=pregunta_id,
                                        version_prompt=version, error=ErrorEstructurado(
                                            error="acceso_denegado", mensaje="Usuario desconocido.",
                                            accion="Verificar el usuario en config/usuarios.json")))
    b = _buscador(buscador)
    fragmentos = b.buscar(pregunta, usuario, CONFIG_RAG["k"])
    maxima = _evidencia_maxima(fragmentos)
    if maxima is None or maxima < CONFIG_RAG["umbral_similitud"]:
        salida = SalidaPregunta(requiere_humano=True, citas=[],
                                respuesta="No hay evidencia suficiente en los documentos disponibles para este usuario.")
        return cerrar(RespuestaPregunta(trace_id=trace_id, ok=True, usuario=usuario, pregunta_id=pregunta_id,
                                        salida=salida, fuentes=_fuentes(fragmentos), version_prompt=version,
                                        evidencia_maxima=maxima))
    sistema = _plantilla("pregunta_rag.md").substitute(evidencia=formatear_evidencia(fragmentos), pregunta=pregunta)
    try:
        proveedor = proveedor or crear_proveedor()
    except ErrorProveedor as exc:
        return cerrar(RespuestaPregunta(trace_id=trace_id, ok=False, usuario=usuario, pregunta_id=pregunta_id,
                                        version_prompt=version, error=ErrorEstructurado(error=exc.tipo,
                                                                                        mensaje=exc.mensaje)))
    herramienta = herramienta_salida(SalidaPregunta, descripcion="Registra la respuesta con sus citas.")
    salida, error, metricas = llamar_con_reintento(proveedor, sistema, f"Pregunta: {pregunta}", herramienta,
                                                   SalidaPregunta, contexto=contexto_fuentes(fragmentos),
                                                   trace_id=trace_id)
    return cerrar(RespuestaPregunta(trace_id=trace_id, ok=salida is not None, usuario=usuario,
                                    pregunta_id=pregunta_id, salida=salida, fuentes=_fuentes(fragmentos),
                                    error=error, metricas=metricas, version_prompt=version,
                                    evidencia_maxima=maxima))


# ------------------------------------------------------------ rastro
def _registrar(r, identificador, impacto, requiere_humano):
    """Una línea por ejecución en logs/ejecuciones.jsonl. Sin el texto del CCAM ni de los fragmentos."""
    ARCHIVO_LOG.parent.mkdir(exist_ok=True)
    registro = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modo": "rag", "trace_id": r.trace_id, "id": identificador, "usuario": r.usuario,
        "roles": roles_de(r.usuario), "version_prompt": r.version_prompt, "ok": r.ok,
        "impacto_propuesto": impacto, "requiere_humano": requiere_humano,
        "fragmentos": [f.fragmento_id for f in r.fuentes], "evidencia_maxima": r.evidencia_maxima,
        "error": r.error.error if r.error else None,
        "campos_fallidos": [c["campo"] for c in r.error.campos] if r.error else [],
        **(r.metricas.model_dump() if r.metricas else {}),
    }
    with ARCHIVO_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return r


# ------------------------------------------------------------ línea de comandos
def main() -> int:
    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser(description="Evalúa un CCAM con los documentos del laboratorio (RAG).")
    p.add_argument("archivo", help="JSON con 'entrada' (ver consultas/)")
    p.add_argument("--usuario", default="u_analista_qa")
    p.add_argument("--simulado", metavar="ESCENARIO", help="rag_valido | rag_sin_evidencia | sin_conexion")
    a = p.parse_args()
    contenido = json.loads(Path(a.archivo).read_text(encoding="utf-8"))
    r = responder(contenido.get("entrada", contenido), a.usuario,
                  ProveedorSimulado(a.simulado) if a.simulado else None)
    print(r.model_dump_json(indent=2, exclude_none=True))
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
