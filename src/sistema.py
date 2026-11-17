"""Sistema de gestión de cambios SIMULADO (PE4): una base SQLite con CCAM ficticios.

QUÉ HACE ESTE ARCHIVO
    Es el "sistema del cliente" de mentira. Guarda los CCAM, los borradores de
    evaluación que se registran y un registro de auditoría de cada escritura.
    Nadie lo toca directo: el único que lo usa es el servidor MCP
    (src/mcp_servidor.py). En la PE5 este archivo se reemplaza por la conexión
    a un sistema legacy y el servidor MCP no cambia.

EQUIVALENTE GxP
    El sistema de gestión de cambios de la planta, en versión de prueba.
    La tabla auditoria es su audit trail: quién, cuándo, qué y con qué datos.

TABLAS
    ccam          un registro por pedido de cambio, con su estado y fecha límite
    evaluaciones  los borradores registrados, con quién lo pidió y quién lo aprobó
    auditoria     una fila por cada escritura (nunca se borra ni se modifica)
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SEMILLA = RAIZ / "datos" / "ccam_semilla.json"
USUARIOS = json.loads((RAIZ / "config" / "usuarios.json").read_text(encoding="utf-8"))
ESTADOS = ("abierto", "en_evaluacion", "borrador_registrado", "vencido", "cerrado")
ROL_APROBADOR = "jefe_qa"
ROLES_SOLICITANTES = ("analista_qa", "jefe_qa")


class ErrorSistema(Exception):
    """Un pedido que el sistema rechaza, con un mensaje para la persona."""


def ruta_base() -> Path:
    return Path(os.getenv("SISTEMA_CCAM_DB", str(RAIZ / "datos" / "sistema_ccam.db")))


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conectar(ruta: Path | None = None) -> sqlite3.Connection:
    """Abre la base; si no existe, la crea desde la semilla."""
    ruta = ruta or ruta_base()
    nueva = not ruta.exists()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    if nueva:
        _crear(con)
    return con


def _crear(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE ccam (
            id_ccam TEXT PRIMARY KEY, tipo_cambio TEXT, area_solicitante TEXT,
            sistema_afectado TEXT, descripcion TEXT, estado TEXT,
            fecha_apertura TEXT, fecha_limite TEXT);
        CREATE TABLE evaluaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_ccam TEXT, impacto TEXT,
            requiere_revalidacion INTEGER, fundamento TEXT, justificacion TEXT,
            solicitado_por TEXT, aprobado_por TEXT, fecha_utc TEXT, estado TEXT);
        CREATE TABLE auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_utc TEXT, usuario TEXT,
            accion TEXT, id_ccam TEXT, detalle TEXT);
    """)
    for c in json.loads(SEMILLA.read_text(encoding="utf-8"))["ccam"]:
        con.execute("INSERT INTO ccam VALUES (?,?,?,?,?,?,?,?)",
                    (c["id_ccam"], c["tipo_cambio"], c["area_solicitante"], c["sistema_afectado"],
                     c["descripcion"], c["estado"], c["fecha_apertura"], c["fecha_limite"]))
    con.execute("INSERT INTO auditoria (fecha_utc, usuario, accion, id_ccam, detalle) VALUES (?,?,?,?,?)",
                (_ahora(), "sistema", "carga_inicial", None, json.dumps({"origen": SEMILLA.name})))
    con.commit()


def rol_de(usuario: str) -> str | None:
    datos = USUARIOS["usuarios"].get(usuario)
    return datos["rol"] if datos else None


# ------------------------------------------------------------ lectura
def consultar(id_ccam: str, con: sqlite3.Connection | None = None) -> dict:
    con = con or conectar()
    fila = con.execute("SELECT * FROM ccam WHERE id_ccam = ?", (id_ccam,)).fetchone()
    if not fila:
        raise ErrorSistema(f"No existe el {id_ccam} en el sistema de gestión de cambios.")
    evals = [dict(e) for e in con.execute(
        "SELECT impacto, fundamento, solicitado_por, aprobado_por, fecha_utc, estado FROM evaluaciones "
        "WHERE id_ccam = ? ORDER BY id", (id_ccam,))]
    for e in evals:
        e["fundamento"] = json.loads(e["fundamento"])
    return {**dict(fila), "evaluaciones_registradas": evals}


def listar(estado: str, con: sqlite3.Connection | None = None) -> list[dict]:
    if estado not in ESTADOS:
        raise ErrorSistema(f"Estado desconocido: {estado}. Válidos: {', '.join(ESTADOS)}.")
    con = con or conectar()
    return [dict(f) for f in con.execute(
        "SELECT id_ccam, tipo_cambio, sistema_afectado, estado, fecha_limite FROM ccam "
        "WHERE estado = ? ORDER BY id_ccam", (estado,))]


# ------------------------------------------------------------ escritura
def registrar_evaluacion(id_ccam: str, impacto: str, requiere_revalidacion: bool, fundamento: list[str],
                         justificacion: str, solicitado_por: str, aprobado_por: str,
                         con: sqlite3.Connection | None = None) -> dict:
    """Registra el borrador. Los controles de segregación se repiten acá aunque el agente ya los haga."""
    con = con or conectar()
    consultar(id_ccam, con)  # existe
    if rol_de(solicitado_por) not in ROLES_SOLICITANTES:
        raise ErrorSistema(f"{solicitado_por} no tiene un rol que pueda pedir el registro de una evaluación.")
    if rol_de(aprobado_por) != ROL_APROBADOR:
        raise ErrorSistema(f"{aprobado_por} no es QA formal (rol {ROL_APROBADOR}): no puede aprobar el registro.")
    if aprobado_por == solicitado_por:
        raise ErrorSistema("Quien pide el registro no puede aprobarlo (segregación de funciones).")
    fecha = _ahora()
    cur = con.execute(
        "INSERT INTO evaluaciones (id_ccam, impacto, requiere_revalidacion, fundamento, justificacion, "
        "solicitado_por, aprobado_por, fecha_utc, estado) VALUES (?,?,?,?,?,?,?,?,?)",
        (id_ccam, impacto, int(requiere_revalidacion), json.dumps(fundamento, ensure_ascii=False), justificacion,
         solicitado_por, aprobado_por, fecha, "BORRADOR_PENDIENTE_QA"))
    con.execute("UPDATE ccam SET estado = 'borrador_registrado' WHERE id_ccam = ?", (id_ccam,))
    con.execute("INSERT INTO auditoria (fecha_utc, usuario, accion, id_ccam, detalle) VALUES (?,?,?,?,?)",
                (fecha, solicitado_por, "registrar_evaluacion", id_ccam,
                 json.dumps({"impacto": impacto, "fundamento": fundamento, "aprobado_por": aprobado_por},
                            ensure_ascii=False)))
    con.commit()
    return {"registrado": True, "id_evaluacion": cur.lastrowid, "id_ccam": id_ccam, "impacto": impacto,
            "estado_ccam": "borrador_registrado", "aprobado_por": aprobado_por, "fecha_utc": fecha,
            "estado_borrador": "BORRADOR_PENDIENTE_QA"}


def auditoria(con: sqlite3.Connection | None = None) -> list[dict]:
    con = con or conectar()
    return [dict(f) for f in con.execute("SELECT * FROM auditoria ORDER BY id")]
