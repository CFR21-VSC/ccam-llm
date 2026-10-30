"""Corre las 5 consultas de consultas/ y arma la tabla de medición de la PE2.

QUÉ HACE
    Para cada archivo consultas/0*.json: llama al motor, anota si validó,
    tokens, costo y latencia, y compara la clasificación con la "esperada"
    (la que marcó el experto de QA dentro de cada archivo). Al final saca
    promedios y los compara con las metas de la PE1.

USO
    python -m scripts.medir                 # con el proveedor del .env (Claude)
    python -m scripts.medir --simulado valido
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.motor import RAIZ, evaluar
from src.proveedores import ProveedorSimulado

META_LATENCIA_MS = 30_000       # HU-01: la propuesta se genera en menos de 30 s
DESEABLE_LATENCIA_MS = 20_000   # HU-01: deseable 20 s
META_COINCIDENCIA = 0.90        # KPI técnico de la PE1 (se mide en serio en la PE6)


def coincide(esperado: dict, propuesta) -> bool:
    """Coincidencia preliminar: misma decisión de alcance y mismo nivel de impacto."""
    if propuesta is None:
        return False
    impacto = propuesta.impacto_gxp.value if propuesta.impacto_gxp else None
    return propuesta.fuera_de_alcance == esperado.get("fuera_de_alcance") and impacto == esperado.get("impacto_gxp")


def main() -> int:
    load_dotenv(RAIZ / ".env")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s", stream=sys.stderr)
    p = argparse.ArgumentParser()
    p.add_argument("--simulado", metavar="ESCENARIO")
    p.add_argument("--pausa", type=float, default=1.0, help="segundos entre consultas (límite de uso)")
    a = p.parse_args()

    archivos = sorted((RAIZ / "consultas").glob("0*.json"))
    filas = []
    for i, archivo in enumerate(archivos, start=1):
        caso = json.loads(archivo.read_text(encoding="utf-8"))
        proveedor = ProveedorSimulado(a.simulado) if a.simulado else None
        r = evaluar(caso["entrada"], proveedor)
        m = r.metricas
        filas.append({
            "n": i, "consulta": caso["nombre"], "tipo": caso.get("tipo_prueba", ""),
            "valido": r.ok, "intentos": m.intentos if m else 0,
            "tokens_entrada": m.input_tokens if m else 0, "tokens_salida": m.output_tokens if m else 0,
            "costo_usd": m.cost if m else None, "latencia_ms": m.latencia_ms if m else None,
            "impacto": (r.propuesta.impacto_gxp.value if r.propuesta and r.propuesta.impacto_gxp
                        else ("fuera_de_alcance" if r.propuesta else None)),
            "confianza": r.propuesta.confianza if r.propuesta else None,
            "esperado": caso.get("esperado", {}).get("impacto_gxp") or
                        ("fuera_de_alcance" if caso.get("esperado", {}).get("fuera_de_alcance") else None),
            "coincide": coincide(caso.get("esperado", {}), r.propuesta),
            "error": r.error.error if r.error else None, "trace_id": r.trace_id, "modelo": m.modelo if m else None,
        })
        print(f"Consulta {i}/{len(archivos)}: {'VALIDÓ' if r.ok else 'ERROR ' + r.error.error}", file=sys.stderr)
        if i < len(archivos):
            time.sleep(a.pausa)

    ok = [f for f in filas if f["valido"]]
    n = len(ok) or 1
    prom = {
        "validas": f"{len(ok)}/{len(filas)}",
        "tokens_entrada": round(sum(f["tokens_entrada"] for f in ok) / n),
        "tokens_salida": round(sum(f["tokens_salida"] for f in ok) / n),
        "costo_usd": round(sum((f["costo_usd"] or 0) for f in ok) / n, 6),
        "latencia_ms": round(sum(f["latencia_ms"] for f in ok) / n),
        "coincidencia": sum(f["coincide"] for f in filas) / len(filas),
    }

    lineas = [
        f"# Medición PE2 — {datetime.now():%Y-%m-%d %H:%M} — modelo {filas[0]['modelo'] if filas else '-'}", "",
        "| # | Consulta | ¿Validó? | Tokens (entrada / salida) | Costo USD | Latencia ms | Impacto propuesto | Esperado |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in filas:
        costo = f"{f['costo_usd']:.6f}" if f["costo_usd"] is not None else "s/d"
        lineas.append(f"| {f['n']} | {f['consulta']} | {'Sí' if f['valido'] else 'No (' + str(f['error']) + ')'} | "
                      f"{f['tokens_entrada']} / {f['tokens_salida']} | {costo} | {f['latencia_ms']} | "
                      f"{f['impacto'] or '-'} | {f['esperado'] or '-'} |")
    lineas += [
        f"| | **Promedio (válidas)** | **{prom['validas']}** | **{prom['tokens_entrada']} / {prom['tokens_salida']}** | "
        f"**{prom['costo_usd']:.6f}** | **{prom['latencia_ms']}** | | |", "",
        "## Comparación con la PE1", "",
        f"- Latencia promedio {prom['latencia_ms']} ms contra la meta de la HU-01 (< {META_LATENCIA_MS} ms; deseable "
        f"< {DESEABLE_LATENCIA_MS} ms): **{'cumple' if prom['latencia_ms'] < META_LATENCIA_MS else 'no cumple'}**.",
        f"- Coincidencia preliminar con la clasificación de QA: {prom['coincidencia']:.0%} contra la meta del KPI "
        f"técnico (≥ {META_COINCIDENCIA:.0%}). Con 5 casos es indicativa; la medición formal es la PE6 (golden dataset).",
    ]
    tabla = "\n".join(lineas)
    print(tabla)

    destino = RAIZ / "resultados"
    destino.mkdir(exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M")
    (destino / f"medicion_{sello}.md").write_text(tabla + "\n", encoding="utf-8")
    (destino / f"medicion_{sello}.json").write_text(json.dumps({"filas": filas, "promedios": prom},
                                                               ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
