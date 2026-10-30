"""Motor de evaluación de impacto de CCAM (Pre-Entrega 2).

QUÉ HACE ESTE ARCHIVO
    Recibe un pedido de cambio (CCAM), se lo pasa a un modelo de lenguaje y
    devuelve una propuesta de evaluación de impacto VALIDADA, junto con lo que
    costó y lo que tardó. Si no puede, devuelve un error estructurado.

EL RECORRIDO DE UN CCAM (función evaluar)
    1. Valida la Entrada contra el contrato     -> si falla, corta acá (no gasta tokens)
    2. Arma los prompts desde las plantillas    -> prompts/sistema.md y prompts/usuario.md
    3. Llama al modelo                          -> src/proveedores.py
    4. Valida la Salida contra el contrato      -> src/contrato.py
       - si falla: anota QUÉ campo falló, se lo devuelve al modelo y reintenta UNA vez
       - si vuelve a fallar: error estructurado "salida_invalida"
    5. Mide tokens (de todos los intentos), costo en USD y latencia en ms
    6. Deja constancia en logs/ejecuciones.jsonl

CON QUIÉN HABLA
    - Usa: src/contrato.py (las reglas), src/proveedores.py (la IA),
           prompts/*.md (las plantillas), config/precios.json (los precios)
    - Lo usan: scripts/medir.py (las 5 consultas) y la línea de comandos
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from src.contrato import CATALOGO_SOPS, Entrada, ErrorEstructurado, Salida
from src.proveedores import ErrorProveedor, Proveedor, ProveedorSimulado, Turno, crear_proveedor

RAIZ = Path(__file__).resolve().parent.parent
DIR_PROMPTS = RAIZ / "prompts"
ARCHIVO_LOG = RAIZ / "logs" / "ejecuciones.jsonl"
MAX_REINTENTOS = 1
NOMBRE_HERRAMIENTA = "registrar_propuesta"

log = logging.getLogger("motor")


# ============================================================ medición
class Metricas(BaseModel):
    modelo: str
    intentos: int
    input_tokens: int          # mismos nombres que la práctica de caché de la unidad 2
    output_tokens: int
    cost: Optional[float]      # USD; None si el modelo no está en config/precios.json
    latencia_ms: int
    cached: bool = False


class Resultado(BaseModel):
    """Lo que entrega el motor, siempre con la misma forma."""
    trace_id: str
    ok: bool
    propuesta: Optional[Salida] = None
    error: Optional[ErrorEstructurado] = None
    metricas: Optional[Metricas] = None
    version_prompt: str


def calcular_costo(modelo: str, tokens_entrada: int, tokens_salida: int) -> Optional[float]:
    """tokens x precio publicado / 1 millón. Los precios viven en config/precios.json."""
    precios = json.loads((RAIZ / "config" / "precios.json").read_text(encoding="utf-8"))["modelos"]
    # la API puede devolver el nombre con sufijo de fecha: se busca por prefijo
    clave = next((m for m in precios if modelo == m or modelo.startswith(m)), None)
    if clave is None:
        log.warning("Modelo %s sin precio en config/precios.json: el costo queda vacío", modelo)
        return None
    p = precios[clave]
    return round((tokens_entrada * p["entrada"] + tokens_salida * p["salida"]) / 1_000_000, 8)


# ============================================================ prompts
def _plantilla(nombre: str) -> Template:
    return Template((DIR_PROMPTS / nombre).read_text(encoding="utf-8"))


def version_prompt() -> str:
    """Huella de las plantillas + catálogo. Si cambia una coma, cambia la versión (trazabilidad)."""
    h = hashlib.sha256()
    for archivo in ("sistema.md", "usuario.md", "correccion.md"):
        h.update((DIR_PROMPTS / archivo).read_bytes())
    h.update((RAIZ / "config" / "catalogo_sops.json").read_bytes())
    return h.hexdigest()[:12]


def armar_prompts(entrada: Entrada) -> tuple[str, str]:
    """Rellena las plantillas: (prompt de sistema, prompt del caso)."""
    catalogo = "\n".join(f"- {c}: {t}" for c, t in CATALOGO_SOPS.items())
    sistema = _plantilla("sistema.md").substitute(catalogo=catalogo)
    usuario = _plantilla("usuario.md").substitute(
        id_ccam=entrada.id_ccam, tipo_cambio=entrada.tipo_cambio.value,
        area_solicitante=entrada.area_solicitante.value,
        sistema_afectado=entrada.sistema_afectado, descripcion=entrada.descripcion)
    return sistema, usuario


def _sin_referencias(esquema: dict) -> dict:
    """Pydantic arma el esquema con referencias internas ($ref); acá se 'aplanan' para la API."""
    definiciones = esquema.pop("$defs", {})

    def resolver(nodo):
        if isinstance(nodo, dict):
            if "$ref" in nodo:
                return resolver(dict(definiciones[nodo["$ref"].split("/")[-1]]))
            return {k: resolver(v) for k, v in nodo.items()}
        if isinstance(nodo, list):
            return [resolver(v) for v in nodo]
        return nodo

    return resolver(esquema)


def herramienta_salida() -> dict:
    """La 'forma' que se le exige al modelo: el esquema JSON de la clase Salida."""
    return {
        "name": NOMBRE_HERRAMIENTA,
        "description": "Registra la propuesta de evaluación de impacto del CCAM como borrador para QA.",
        "input_schema": _sin_referencias(Salida.model_json_schema()),
    }


# ============================================================ errores
def campos_fallidos(exc: ValidationError) -> list[dict]:
    """Traduce un ValidationError a [{campo, problema}] usando loc. Sin el dato original (privacidad)."""
    return [{"campo": " -> ".join(map(str, e["loc"])) or "(regla cruzada)", "problema": e["msg"]}
            for e in exc.errors(include_input=False)]


# ============================================================ el motor
def evaluar(datos: dict, proveedor: Optional[Proveedor] = None) -> Resultado:
    trace_id = uuid.uuid4().hex[:12]
    version = version_prompt()

    # 1. Entrada: si viene mal, se corta acá sin llamar al modelo (costo cero).
    try:
        entrada = Entrada.model_validate(datos)
    except ValidationError as exc:
        error = ErrorEstructurado(error="entrada_invalida", mensaje="El pedido no cumple el contrato de Entrada.",
                                  campos=campos_fallidos(exc), accion="Corregir el pedido y volver a enviarlo")
        return _cerrar(Resultado(trace_id=trace_id, ok=False, error=error, version_prompt=version), datos)

    try:
        proveedor = proveedor or crear_proveedor()
    except ErrorProveedor as exc:  # por ejemplo, falta la clave
        error = ErrorEstructurado(error=exc.tipo, mensaje=exc.mensaje)
        return _cerrar(Resultado(trace_id=trace_id, ok=False, error=error, version_prompt=version), datos)
    except Exception as exc:  # paquete faltante o LLM_PROVIDER mal escrito
        error = ErrorEstructurado(error="configuracion", mensaje=str(exc))
        return _cerrar(Resultado(trace_id=trace_id, ok=False, error=error, version_prompt=version), datos)

    # 2. Prompts desde plantillas.
    sistema, usuario = armar_prompts(entrada)
    turnos = [Turno("usuario", usuario)]
    herramienta = herramienta_salida()

    tokens_in = tokens_out = 0
    modelo = getattr(proveedor, "modelo", "desconocido")
    inicio = time.perf_counter()
    fallas: list[dict] = []

    for intento in range(1, MAX_REINTENTOS + 2):
        # 3. Llamada al modelo.
        try:
            r = proveedor.generar(sistema, turnos, herramienta)
        except ErrorProveedor as exc:
            log.error("[%s] intento %d: error de API (%s) %s", trace_id, intento, exc.tipo, exc.mensaje)
            error = ErrorEstructurado(error=exc.tipo, mensaje=exc.mensaje, intentos=intento)
            metricas = Metricas(modelo=modelo, intentos=intento, input_tokens=tokens_in, output_tokens=tokens_out,
                                cost=calcular_costo(modelo, tokens_in, tokens_out),
                                latencia_ms=round((time.perf_counter() - inicio) * 1000))
            return _cerrar(Resultado(trace_id=trace_id, ok=False, error=error, metricas=metricas,
                                     version_prompt=version), datos)

        tokens_in += r.tokens_entrada       # los reintentos también se pagan: se acumula
        tokens_out += r.tokens_salida
        modelo = r.modelo

        # 4. Validación de la salida.
        try:
            if r.corte_por_largo:
                raise ValueError("la respuesta se cortó por max_tokens")
            if r.datos is None:
                raise ValueError("el modelo no usó la herramienta registrar_propuesta")
            propuesta = Salida.model_validate(r.datos)
        except (ValidationError, ValueError) as exc:
            fallas = (campos_fallidos(exc) if isinstance(exc, ValidationError)
                      else [{"campo": "(respuesta)", "problema": str(exc)}])
            for f in fallas:
                log.warning("[%s] intento %d/%d: salida inválida -> %s: %s",
                            trace_id, intento, MAX_REINTENTOS + 1, f["campo"], f["problema"])
            if intento <= MAX_REINTENTOS:
                detalle = "\n".join(f"- {f['campo']}: {f['problema']}" for f in fallas)
                turnos += [Turno("modelo", respuesta=r),
                           Turno("error_validacion", _plantilla("correccion.md").substitute(errores=detalle))]
                continue
            break

        # 5. Éxito: se mide y se devuelve.
        metricas = Metricas(modelo=modelo, intentos=intento, input_tokens=tokens_in, output_tokens=tokens_out,
                            cost=calcular_costo(modelo, tokens_in, tokens_out),
                            latencia_ms=round((time.perf_counter() - inicio) * 1000))
        return _cerrar(Resultado(trace_id=trace_id, ok=True, propuesta=propuesta, metricas=metricas,
                                 version_prompt=version), datos)

    # Agotó el reintento: error estructurado, nunca un traceback.
    error = ErrorEstructurado(error="salida_invalida", intentos=MAX_REINTENTOS + 1, campos=fallas,
                              mensaje="El modelo no produjo una propuesta válida después del reintento.")
    metricas = Metricas(modelo=modelo, intentos=MAX_REINTENTOS + 1, input_tokens=tokens_in, output_tokens=tokens_out,
                        cost=calcular_costo(modelo, tokens_in, tokens_out),
                        latencia_ms=round((time.perf_counter() - inicio) * 1000))
    return _cerrar(Resultado(trace_id=trace_id, ok=False, error=error, metricas=metricas,
                             version_prompt=version), datos)


def _cerrar(resultado: Resultado, datos: dict) -> Resultado:
    """6. Deja constancia de la ejecución (una línea por CCAM). Sin la descripción: solo metadatos."""
    ARCHIVO_LOG.parent.mkdir(exist_ok=True)
    registro = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trace_id": resultado.trace_id,
        "id_ccam": datos.get("id_ccam") if isinstance(datos, dict) else None,
        "version_prompt": resultado.version_prompt,
        "ok": resultado.ok,
        "impacto_propuesto": resultado.propuesta.impacto_gxp.value
        if resultado.propuesta and resultado.propuesta.impacto_gxp else None,
        "error": resultado.error.error if resultado.error else None,
        "campos_fallidos": [c["campo"] for c in resultado.error.campos] if resultado.error else [],
        **(resultado.metricas.model_dump() if resultado.metricas else {}),
    }
    with ARCHIVO_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return resultado


# ============================================================ línea de comandos
def main() -> int:
    load_dotenv(RAIZ / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    p = argparse.ArgumentParser(description="Evalúa el impacto de un CCAM (archivo JSON).")
    p.add_argument("archivo", help="JSON con 'entrada' (ver carpeta consultas/)")
    p.add_argument("--simulado", metavar="ESCENARIO",
                   help="usa el proveedor simulado: valido | invalido | invalido_luego_valido | sin_conexion | limite_uso")
    a = p.parse_args()

    contenido = json.loads(Path(a.archivo).read_text(encoding="utf-8"))
    datos = contenido.get("entrada", contenido)
    proveedor = ProveedorSimulado(a.simulado) if a.simulado else None
    r = evaluar(datos, proveedor)

    print(r.model_dump_json(indent=2, exclude_none=True))
    if r.metricas:
        m = r.metricas
        costo = f"USD {m.cost:.6f}" if m.cost is not None else "USD s/d"
        print(f"\n{'VALIDADO' if r.ok else 'ERROR ' + r.error.error} | modelo {m.modelo} | intentos {m.intentos} | "
              f"tokens {m.input_tokens}/{m.output_tokens} | {costo} | {m.latencia_ms} ms | trace {r.trace_id}",
              file=sys.stderr)
    elif r.error:
        print(f"\nERROR {r.error.error} | sin llamada al modelo | trace {r.trace_id}", file=sys.stderr)
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
