"""Proveedores de modelos de lenguaje (el "enchufe" hacia la IA).

QUÉ HACE ESTE ARCHIVO
    Es el único lugar del sistema que sabe hablar con una empresa de IA
    (Anthropic, OpenAI) o con el simulador. El motor le pide "generá una
    propuesta" y este archivo se encarga de los detalles de cada proveedor.

CON QUIÉN HABLA
    - Lo llama: src/motor.py
    - Llama a:  la API de Anthropic, la de OpenAI o a nadie (modo simulado)

POR QUÉ ESTÁ SEPARADO
    Si mañana cambiamos de Claude a otro modelo, solo se toca este archivo.
    El contrato, la validación, el reintento y la medición no se enteran.
    (RFC-000, principio 4: el modelo de IA es un Connector más.)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


# --------------------------------------------------------------------------
# Lo que todo proveedor devuelve, sea quien sea (el "formulario de respuesta").
# --------------------------------------------------------------------------
@dataclass
class RespuestaModelo:
    datos: Optional[dict]          # la propuesta tal como vino (todavía SIN validar)
    tokens_entrada: int            # sale del campo "usage" de la API
    tokens_salida: int
    modelo: str
    corte_por_largo: bool = False  # True si el modelo se quedó sin max_tokens a mitad de la respuesta
    crudo: Any = None              # la respuesta original, para poder armar el reintento


@dataclass
class Turno:
    """Un mensaje de la conversación con el modelo.

    tipo = "usuario"           -> el pedido de cambio
    tipo = "modelo"            -> lo que respondió el modelo (para el reintento)
    tipo = "error_validacion"  -> le avisamos qué campos fallaron
    """
    tipo: str
    texto: str = ""
    respuesta: Optional[RespuestaModelo] = None


class ErrorProveedor(Exception):
    """Falla de la API (no del contenido). tipo: api_limite_uso, api_sin_conexion, api_autenticacion, api_error."""

    def __init__(self, tipo: str, mensaje: str):
        super().__init__(mensaje)
        self.tipo = tipo
        self.mensaje = mensaje


class Proveedor(Protocol):
    """Cualquier proveedor tiene que saber hacer esto y nada más."""
    modelo: str

    def generar(self, sistema: str, turnos: list[Turno], herramienta: dict) -> RespuestaModelo: ...


# --------------------------------------------------------------------------
# Anthropic (Claude) — el proveedor que usamos en la PE2.
# --------------------------------------------------------------------------
class ProveedorAnthropic:
    """Claude. OJO: desde la versión 2026-10-21 de la API, Claude ya NO acepta
    temperature/top_p/top_k (responde error 400). Siempre muestrea con sus valores
    por defecto. Por eso la reproducibilidad no se controla acá: se controla con el
    contrato, el catálogo cerrado de SOPs y el reintento (y se mide en la PE6)."""

    def __init__(self, modelo: str, max_tokens: int = 3000):
        import anthropic  # se importa acá para que el modo simulado funcione sin instalarlo

        self._sdk = anthropic
        # La clave NO está en el código: la librería la lee sola de la variable ANTHROPIC_API_KEY.
        # Si falta, se corta acá con un error claro (sin esto la librería tira un traceback).
        if not os.getenv("ANTHROPIC_API_KEY", "").strip():
            raise ErrorProveedor("api_autenticacion", "Falta ANTHROPIC_API_KEY en el archivo .env.")
        self._cliente = anthropic.Anthropic(max_retries=0, timeout=60.0)
        self.modelo = modelo
        self.max_tokens = max_tokens

    def _a_mensajes(self, turnos: list[Turno]) -> list[dict]:
        """Traduce nuestra conversación al formato que entiende Claude."""
        mensajes: list[dict] = []
        ultimo_id = None
        for t in turnos:
            if t.tipo == "usuario":
                mensajes.append({"role": "user", "content": t.texto})
            elif t.tipo == "modelo" and t.respuesta is not None:
                bloques = [b.model_dump(exclude_none=True) for b in t.respuesta.crudo.content]
                mensajes.append({"role": "assistant", "content": bloques})
                ultimo_id = next((b.id for b in t.respuesta.crudo.content if b.type == "tool_use"), None)
            elif t.tipo == "error_validacion":
                if ultimo_id:  # le devolvemos el error "atado" a su respuesta anterior
                    mensajes.append({"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": ultimo_id, "is_error": True, "content": t.texto}]})
                else:
                    mensajes.append({"role": "user", "content": t.texto})
        return mensajes

    def generar(self, sistema: str, turnos: list[Turno], herramienta: dict) -> RespuestaModelo:
        sdk = self._sdk
        try:
            r = self._cliente.messages.create(
                model=self.modelo,
                max_tokens=self.max_tokens,          # techo de la respuesta (sin temperature: ver arriba)
                system=sistema,                     # las reglas fijas (prompts/sistema.md)
                messages=self._a_mensajes(turnos),   # el caso puntual (y el reintento, si hay)
                tools=[herramienta],                 # la "forma" de la respuesta (esquema de Salida)
                tool_choice={"type": "tool", "name": herramienta["name"]},  # obligado a usarla
            )
        except sdk.RateLimitError as e:
            raise ErrorProveedor("api_limite_uso", "Se alcanzó el límite de uso de la API; reintentar más tarde.") from e
        except (sdk.APIConnectionError, sdk.APITimeoutError) as e:
            raise ErrorProveedor("api_sin_conexion", "No hay conexión con la API o no respondió a tiempo.") from e
        except (sdk.AuthenticationError, sdk.PermissionDeniedError) as e:
            raise ErrorProveedor("api_autenticacion", "La clave ANTHROPIC_API_KEY falta, es inválida o no tiene permisos.") from e
        except sdk.APIStatusError as e:
            raise ErrorProveedor("api_error", f"La API respondió con error HTTP {e.status_code}.") from e

        bloque = next((b for b in r.content if b.type == "tool_use"), None)
        return RespuestaModelo(
            datos=dict(bloque.input) if bloque else None,
            tokens_entrada=r.usage.input_tokens,
            tokens_salida=r.usage.output_tokens,
            modelo=r.model,
            corte_por_largo=(r.stop_reason == "max_tokens"),
            crudo=r,
        )


# --------------------------------------------------------------------------
# OpenAI — opcional (extra de la consigna). Mismo contrato, otra sintaxis.
# --------------------------------------------------------------------------
class ProveedorOpenAI:
    def __init__(self, modelo: str, temperatura: float = 0.0, max_tokens: int = 3000):
        import openai

        self._sdk = openai
        self._cliente = openai.OpenAI(max_retries=0, timeout=60.0)  # lee OPENAI_API_KEY
        self.modelo = modelo
        self.temperatura = temperatura
        self.max_tokens = max_tokens

    def generar(self, sistema: str, turnos: list[Turno], herramienta: dict) -> RespuestaModelo:
        sdk = self._sdk
        mensajes: list[dict] = [{"role": "system", "content": sistema}]
        ultimo_id = None
        for t in turnos:
            if t.tipo == "usuario":
                mensajes.append({"role": "user", "content": t.texto})
            elif t.tipo == "modelo" and t.respuesta is not None:
                msg = t.respuesta.crudo.choices[0].message
                mensajes.append(msg.model_dump(exclude_none=True))
                ultimo_id = msg.tool_calls[0].id if msg.tool_calls else None
            elif t.tipo == "error_validacion":
                mensajes.append({"role": "tool", "tool_call_id": ultimo_id, "content": t.texto} if ultimo_id
                                else {"role": "user", "content": t.texto})
        funcion = {"type": "function", "function": {
            "name": herramienta["name"], "description": herramienta["description"],
            "parameters": herramienta["input_schema"]}}
        try:
            r = self._cliente.chat.completions.create(
                model=self.modelo, temperature=self.temperatura, max_tokens=self.max_tokens,
                messages=mensajes, tools=[funcion],
                tool_choice={"type": "function", "function": {"name": herramienta["name"]}})
        except sdk.RateLimitError as e:
            raise ErrorProveedor("api_limite_uso", "Se alcanzó el límite de uso de la API.") from e
        except (sdk.APIConnectionError, sdk.APITimeoutError) as e:
            raise ErrorProveedor("api_sin_conexion", "No hay conexión con la API.") from e
        except (sdk.AuthenticationError, sdk.PermissionDeniedError) as e:
            raise ErrorProveedor("api_autenticacion", "La clave OPENAI_API_KEY falta o es inválida.") from e
        except sdk.APIStatusError as e:
            raise ErrorProveedor("api_error", f"La API respondió con error HTTP {e.status_code}.") from e
        choice = r.choices[0]
        llamada = choice.message.tool_calls[0] if choice.message.tool_calls else None
        try:
            datos = json.loads(llamada.function.arguments) if llamada else None
        except json.JSONDecodeError:
            datos = None
        return RespuestaModelo(datos=datos, tokens_entrada=r.usage.prompt_tokens,
                               tokens_salida=r.usage.completion_tokens, modelo=r.model,
                               corte_por_largo=(choice.finish_reason == "length"), crudo=r)


# --------------------------------------------------------------------------
# Simulado — funciona sin clave y sin internet. Sirve para probar el motor
# y para mostrar el camino de error sin gastar tokens.
# --------------------------------------------------------------------------
_PROPUESTA_VALIDA = {
    "fuera_de_alcance": False, "impacto_gxp": "mayor", "requiere_revalidacion": True,
    "justificacion": "Respuesta simulada: el cambio afecta un sistema validado y requiere evaluar el impacto sobre los registros electrónicos.",
    "fundamento": [{"codigo": "SOP-VS-002", "seccion": "6.3"}],
    "tareas": [{"descripcion": "Evaluación de riesgo de la nueva versión del sistema", "area_responsable": "validaciones"}],
    "confianza": 0.8, "estado": "BORRADOR_PENDIENTE_QA",
}
_PROPUESTA_INVALIDA = {  # cita un SOP que no existe y no propone tareas para un impacto mayor
    **_PROPUESTA_VALIDA, "fundamento": [{"codigo": "SOP-QA-099", "seccion": "1"}], "tareas": [],
}
_ESCENARIOS = {
    "valido": [_PROPUESTA_VALIDA],
    "invalido": [_PROPUESTA_INVALIDA, _PROPUESTA_INVALIDA],
    "invalido_luego_valido": [_PROPUESTA_INVALIDA, _PROPUESTA_VALIDA],
}


@dataclass
class ProveedorSimulado:
    escenario: str = "valido"
    modelo: str = "simulado"
    _llamadas: int = field(default=0, init=False)

    def generar(self, sistema: str, turnos: list[Turno], herramienta: dict) -> RespuestaModelo:
        if self.escenario == "sin_conexion":
            raise ErrorProveedor("api_sin_conexion", "Simulación: no hay conexión con la API.")
        if self.escenario == "limite_uso":
            raise ErrorProveedor("api_limite_uso", "Simulación: se alcanzó el límite de uso de la API.")
        secuencia = _ESCENARIOS.get(self.escenario, _ESCENARIOS["valido"])
        datos = secuencia[min(self._llamadas, len(secuencia) - 1)]
        self._llamadas += 1
        time.sleep(0.05)
        texto_entrada = sistema + "".join(t.texto for t in turnos) + json.dumps(herramienta)
        return RespuestaModelo(datos=json.loads(json.dumps(datos)),
                               tokens_entrada=len(texto_entrada) // 4,       # estimación: no hay API real
                               tokens_salida=len(json.dumps(datos)) // 4,
                               modelo=self.modelo)


def crear_proveedor() -> Proveedor:
    """Elige el proveedor según el archivo .env (LLM_PROVIDER y LLM_MODEL)."""
    nombre = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
    temperatura = float(os.getenv("LLM_TEMPERATURE", "0"))  # solo la usa OpenAI; Claude ya no la acepta
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "3000"))
    if nombre == "anthropic":
        return ProveedorAnthropic(os.getenv("LLM_MODEL", "claude-haiku-5-5"), max_tokens)
    if nombre == "openai":
        return ProveedorOpenAI(os.getenv("LLM_MODEL", "gpt-4o-mini"), temperatura, max_tokens)
    if nombre == "simulado":
        return ProveedorSimulado(os.getenv("SIMULADO_ESCENARIO", "valido"))
    raise ValueError(f"LLM_PROVIDER desconocido: {nombre!r} (usar anthropic, openai o simulado)")
