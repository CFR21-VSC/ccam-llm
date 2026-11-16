"""Corrida única de medición: una sola fuente de verdad para el PDF.

QUÉ HACE
    Corre todos los CCAM de consultas/ y los casos de error, UNA vez cada uno,
    y guarda todo en una carpeta nueva:

        resultados/corrida_AAAAMMDD_HHMM/
            caso_NN.txt        salida de terminal completa, sin recortar
            caso_NN.json       el Resultado completo de esa misma ejecución
            error_reintento.txt / error_api.txt / error_entrada.txt
            medicion.md        tabla y comparación con la PE1
            medicion.json      lo mismo en datos, armado leyendo los caso_NN.json
            manifiesto.json    fecha, modelo, versión del prompt, commit y hash de cada archivo

    La tabla nunca hace otra llamada: se arma leyendo los caso_NN.json de la
    misma carpeta. Así la ejecución que muestra el PDF y la fila de la tabla
    son el mismo dato (devolución de la PE2).

POR QUÉ CON SUBPROCESOS
    Cada caso se corre igual que lo correría una persona
    (python -m src.motor archivo.json): el .txt es la terminal real y el .json
    es lo que imprimió esa misma ejecución.

USO
    python -m scripts.corrida                     # con el proveedor de .env (Claude)
    python -m scripts.corrida --simulado valido   # sin clave ni internet (pruebas y CI)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
PENDIENTE_QA = "A_CONFIRMAR_POR_QA"

META_LATENCIA_MS = 30_000        # HU-01: menos de 30 s
DESEABLE_LATENCIA_MS = 20_000    # HU-01: deseable 20 s
META_COINCIDENCIA = 0.90         # KPI técnico de la PE1
CASOS_PE2 = {"01", "02", "03", "04", "05"}


# ------------------------------------------------------------ ejecución
def _correr(argumentos: list[str], variables: dict | None = None) -> tuple[str, dict | None]:
    """Corre el motor como lo haría una persona. Devuelve (terminal completa, JSON impreso)."""
    entorno = {**os.environ, **(variables or {}), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-m", "src.motor", *argumentos], cwd=RAIZ, env=entorno,
                       capture_output=True, text=True, encoding="utf-8")
    terminal = "$ python -m src.motor " + " ".join(argumentos) + "\n" + r.stderr + r.stdout
    try:
        datos = json.loads(r.stdout)
    except json.JSONDecodeError:
        datos = None
    return terminal, datos


def casos_a_correr() -> tuple[list[Path], list[str]]:
    """Los CCAM numerados de consultas/ (no los de extra/). Saltea los que QA no clasificó."""
    elegidos, salteados = [], []
    for archivo in sorted((RAIZ / "consultas").glob("[0-9][0-9]_*.json")):
        esperado = json.loads(archivo.read_text(encoding="utf-8")).get("esperado", {})
        if esperado.get("impacto_gxp") == PENDIENTE_QA:
            salteados.append(archivo.name)
        else:
            elegidos.append(archivo)
    return elegidos, salteados


# ------------------------------------------------------------ medición
def grupo_de(numero: str, caso: dict) -> str:
    if numero in CASOS_PE2:
        return "pe2_originales"
    return "anclas" if caso.get("tipo_prueba") == "ancla" else "frontera"


def nivel(propuesta: dict | None) -> str | None:
    if not propuesta:
        return None
    return "fuera_de_alcance" if propuesta.get("fuera_de_alcance") else propuesta.get("impacto_gxp")


def nivel_esperado(esperado: dict) -> str | None:
    return "fuera_de_alcance" if esperado.get("fuera_de_alcance") else esperado.get("impacto_gxp")


def armar_medicion(carpeta: Path, casos: list[Path]) -> dict:
    """Lee SOLO los caso_NN.json de la carpeta. Nunca llama al modelo."""
    filas = []
    for archivo in casos:
        numero = archivo.name[:2]
        caso = json.loads(archivo.read_text(encoding="utf-8"))
        r = json.loads((carpeta / f"caso_{numero}.json").read_text(encoding="utf-8"))
        m, p, esp = r.get("metricas") or {}, r.get("propuesta"), caso.get("esperado", {})
        propuesto, esperado = nivel(p), nivel_esperado(esp)
        filas.append({
            "n": numero, "archivo": archivo.name, "consulta": caso.get("nombre", archivo.stem),
            "grupo": grupo_de(numero, caso), "valido": bool(r.get("ok")),
            "error": (r.get("error") or {}).get("error"), "intentos": m.get("intentos", 0),
            "tokens_entrada": m.get("input_tokens", 0), "tokens_salida": m.get("output_tokens", 0),
            "costo_usd": m.get("cost"), "latencia_ms": m.get("latencia_ms"),
            "confianza": p.get("confianza") if p else None,
            "propuesto": propuesto, "esperado": esperado,
            "coincide": p is not None and propuesto == esperado,
            "revalidacion_propuesta": p.get("requiere_revalidacion") if p else None,
            "revalidacion_esperada": esp.get("requiere_revalidacion"),
            "trace_id": r.get("trace_id"), "modelo": m.get("modelo"),
        })

    def coincidencia(sub: list[dict]) -> dict:
        return {"aciertos": sum(f["coincide"] for f in sub), "total": len(sub),
                "porcentaje": round(sum(f["coincide"] for f in sub) / len(sub), 4) if sub else None}

    validas = [f for f in filas if f["valido"]]
    n = len(validas) or 1
    promedios = {
        "validas": len(validas), "total": len(filas),
        "tokens_entrada": round(sum(f["tokens_entrada"] for f in validas) / n),
        "tokens_salida": round(sum(f["tokens_salida"] for f in validas) / n),
        "costo_usd": round(sum((f["costo_usd"] or 0) for f in validas) / n, 6),
        "latencia_ms": round(sum(f["latencia_ms"] or 0 for f in validas) / n),
        "latencia_max_ms": max((f["latencia_ms"] or 0 for f in validas), default=0),
    }
    por_grupo = {g: coincidencia([f for f in filas if f["grupo"] == g])
                 for g in ("pe2_originales", "anclas", "frontera") if any(f["grupo"] == g for f in filas)}
    niveles = ["sin_impacto", "menor", "mayor", "critico", "fuera_de_alcance"]
    por_nivel = {nv: coincidencia([f for f in filas if f["esperado"] == nv])
                 for nv in niveles if any(f["esperado"] == nv for f in filas)}
    orden = {nv: i for i, nv in enumerate(["sin_impacto", "menor", "mayor", "critico"])}
    sesgo = {"sobreclasifica": 0, "subclasifica": 0}
    for f in filas:
        if f["propuesto"] in orden and f["esperado"] in orden and f["propuesto"] != f["esperado"]:
            sesgo["sobreclasifica" if orden[f["propuesto"]] > orden[f["esperado"]] else "subclasifica"] += 1
    return {"filas": filas, "promedios": promedios, "coincidencia_total": coincidencia(filas),
            "coincidencia_por_grupo": por_grupo, "coincidencia_por_nivel": por_nivel, "sesgo": sesgo,
            "modelo": next((f["modelo"] for f in filas if f["modelo"]), None)}


def medicion_md(med: dict, fecha: str) -> str:
    p, ct = med["promedios"], med["coincidencia_total"]
    pct = lambda c: f"{c['aciertos']}/{c['total']} ({c['porcentaje']:.0%})" if c["total"] else "-"
    lineas = [
        f"# Medición — {fecha} — modelo {med['modelo']}", "",
        "Armada leyendo los `caso_NN.json` de esta misma carpeta: cada fila es la ejecución de su `caso_NN.txt`.", "",
        "| # | Consulta | Grupo | ¿Validó? | Intentos | Tokens entrada / salida | Costo USD | Latencia ms | Confianza | Propuesto | Esperado QA | Coincide |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in med["filas"]:
        costo = f"{f['costo_usd']:.6f}" if f["costo_usd"] is not None else "s/d"
        ok = "Sí" if f["valido"] else f"No ({f['error']})"
        lineas.append(f"| {f['n']} | {f['consulta']} | {f['grupo']} | {ok} | {f['intentos']} | "
                      f"{f['tokens_entrada']} / {f['tokens_salida']} | {costo} | {f['latencia_ms']} | "
                      f"{f['confianza'] if f['confianza'] is not None else '-'} | {f['propuesto'] or '-'} | "
                      f"{f['esperado'] or '-'} | {'Sí' if f['coincide'] else 'No'} |")
    lineas += [
        f"| | **Promedio de las válidas** | | **{p['validas']}/{p['total']}** | | **{p['tokens_entrada']} / {p['tokens_salida']}** | "
        f"**{p['costo_usd']:.6f}** | **{p['latencia_ms']}** | | | | **{pct(ct)}** |", "",
        "## Coincidencia con QA", "",
        "| Corte | Aciertos |", "|---|---|",
        f"| Total | {pct(ct)} |",
        *[f"| Grupo: {g} | {pct(c)} |" for g, c in med["coincidencia_por_grupo"].items()],
        *[f"| Nivel esperado: {nv} | {pct(c)} |" for nv, c in med["coincidencia_por_nivel"].items()],
        "", f"Discrepancias de nivel: {med['sesgo']['sobreclasifica']} sobreclasificaciones y "
            f"{med['sesgo']['subclasifica']} subclasificaciones.", "",
        "## Comparación con la PE1", "",
        f"- Latencia promedio {p['latencia_ms']} ms (peor caso {p['latencia_max_ms']} ms) contra la meta de la HU-01 "
        f"(< {META_LATENCIA_MS} ms; deseable < {DESEABLE_LATENCIA_MS} ms): "
        f"**{'cumple' if p['latencia_max_ms'] < META_LATENCIA_MS else 'no cumple'}**.",
        f"- Coincidencia con QA: {pct(ct)} contra la meta del KPI técnico (≥ {META_COINCIDENCIA:.0%}). "
        "Es indicativa; la medición formal es la PE6 con golden dataset.",
    ]
    return "\n".join(lineas) + "\n"


# ------------------------------------------------------------ manifiesto
def sha256(archivo: Path) -> str:
    return hashlib.sha256(archivo.read_bytes()).hexdigest()


def commit_actual() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True)
        return r.stdout.strip() or None
    except OSError:
        return None


def escribir_manifiesto(carpeta: Path, med: dict, salteados: list[str], simulado: str | None) -> None:
    from src.motor import version_prompt
    archivos = sorted(f for f in carpeta.iterdir() if f.is_file() and f.name != "manifiesto.json")
    manifiesto = {
        "corrida": carpeta.name, "fecha": datetime.now().isoformat(timespec="seconds"),
        "modelo": med["modelo"], "modo": f"simulado:{simulado}" if simulado else "real",
        "version_prompt": version_prompt(), "commit": commit_actual(),
        "casos": len(med["filas"]), "casos_salteados_sin_clasificar": salteados,
        "archivos": {f.name: sha256(f) for f in archivos},
    }
    (carpeta / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")


# ------------------------------------------------------------ programa
def correr(simulado: str | None = None, pausa: float = 1.0, destino: Path | None = None) -> Path:
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    carpeta = destino or (RAIZ / "resultados" / f"corrida_{fecha}")
    carpeta.mkdir(parents=True, exist_ok=False)
    extra = ["--simulado", simulado] if simulado else []

    casos, salteados = casos_a_correr()
    for nombre in salteados:
        print(f"Salteado (sin clasificar por QA): {nombre}", file=sys.stderr)
    for i, archivo in enumerate(casos, start=1):
        numero = archivo.name[:2]
        terminal, datos = _correr([f"consultas/{archivo.name}", *extra])
        (carpeta / f"caso_{numero}.txt").write_text(terminal, encoding="utf-8")
        (carpeta / f"caso_{numero}.json").write_text(
            json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        estado = "VALIDÓ" if datos and datos.get("ok") else f"ERROR {((datos or {}).get('error') or {}).get('error')}"
        print(f"Caso {numero} ({i}/{len(casos)}): {estado}", file=sys.stderr)
        if i < len(casos) and not simulado:
            time.sleep(pausa)

    errores = {
        "error_reintento": (["consultas/01_version_software.json", "--simulado", "invalido"], {}),
        "error_api": ((["consultas/01_version_software.json", "--simulado", "sin_conexion"], {}) if simulado else
                      (["consultas/01_version_software.json"],
                       {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-ant-clave-invalida-de-prueba"})),
        "error_entrada": (["consultas/extra/entrada_invalida.json", "--simulado", "valido"], {}),
    }
    for nombre, (argumentos, variables) in errores.items():
        terminal, _ = _correr(argumentos, variables)
        (carpeta / f"{nombre}.txt").write_text(terminal, encoding="utf-8")

    med = armar_medicion(carpeta, casos)
    (carpeta / "medicion.json").write_text(json.dumps(med, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    texto = medicion_md(med, datetime.now().strftime("%Y-%m-%d %H:%M"))
    (carpeta / "medicion.md").write_text(texto, encoding="utf-8")
    escribir_manifiesto(carpeta, med, salteados, simulado)
    print(texto)
    mostrar = carpeta.relative_to(RAIZ) if carpeta.is_relative_to(RAIZ) else carpeta
    print(f"Corrida guardada en {mostrar}", file=sys.stderr)
    return carpeta


def main() -> int:
    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser(description="Corrida única de medición y evidencia.")
    p.add_argument("--simulado", metavar="ESCENARIO", help="sin clave: valido | invalido_luego_valido | ...")
    p.add_argument("--pausa", type=float, default=1.0, help="segundos entre llamadas reales (límite de uso)")
    a = p.parse_args()
    correr(a.simulado, a.pausa)
    return 0


if __name__ == "__main__":
    sys.exit(main())
