"""Corrida de las correcciones de la devolución de la PE3, en una sola carpeta.

QUÉ HACE (y a qué punto de la devolución responde)
    0. Verifica que el corpus sea el congelado (evals/corpus_congelado.json). Si cambió, no corre.
    1. M-1  Fragmentado A y B: método, separadores, solapamiento y tokens reales por fragmento.
    2. M-2/M-5  Top-k por pregunta: los 5 primeros fragmentos de cada una de las 10 preguntas,
               el puesto del primer acierto y el acierto @3/@5 según la definición formal.
    3. M-5/M-6  Matriz de seguridad rol × documento restringido, con consultas directas y
               parafraseadas: fugas en resultados, fugas en el prompt y control positivo.
    4. M-4  Los 10 CCAM nuevos (consultas_nuevas/) con el corpus congelado, contra la
               clasificación de QA. Si falta alguna clasificación, no corre esta parte.
    5. M-3  El objeto completo que devuelve responder() para un CCAM, con fuentes y fundamento.
    6. manifiesto.json con commit, versión de prompt, hash del corpus y hash de cada archivo.

USO
    python -m scripts.corrida_correcciones_pe3                 # con Claude y embeddings locales
    python -m scripts.corrida_correcciones_pe3 --simulado      # sin clave ni descarga (prueba)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scripts.corrida import commit_actual, sha256
from scripts.corrida_pe3 import KS, acierta
from src.proveedores import ProveedorSimulado
from src.rag.buscar import USUARIOS, Buscador, roles_de
from src.rag.corpus import leer_carpeta
from src.rag.embeddings import crear_embedder
from src.rag.ingestar import CONFIG_RAG, RAIZ, ingestar
from src.rag.responder import responder, responder_pregunta, version_prompt_rag

NIVELES = ["sin_impacto", "menor", "mayor", "critico"]
USUARIO_DE_ROL = {d["rol"]: u for u, d in USUARIOS["usuarios"].items()}


def _json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hash_corpus() -> tuple[str, dict]:
    docs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((RAIZ / "documentos").glob("*.md"))}
    return hashlib.sha256("".join(f"{k}:{v}\n" for k, v in docs.items()).encode()).hexdigest(), docs


# ------------------------------------------------------------ 1. fragmentado
def fragmentado(carpeta: Path) -> dict:
    salida = {}
    for config in ("A", "B"):
        m = json.loads((carpeta / f"ingesta_{config}.json").read_text(encoding="utf-8"))
        tokens = [t for d in m["documentos"] for t in d["tokens_por_fragmento"]]
        c = CONFIG_RAG["configuraciones"][config]
        salida[config] = {
            "tope_tokens": c["max_tokens"], "solapamiento": c["solapamiento"], "metodo_corte": c["metodo_corte"],
            "separadores": c["separadores"], "solapamiento_detalle": c["solapamiento_detalle"], "prefijo": c["prefijo"],
            "fragmentos": m["total_fragmentos"], "tokens_min": min(tokens), "tokens_mediana": int(statistics.median(tokens)),
            "tokens_max": max(tokens),
            "documentos_en_un_solo_fragmento": sum(1 for d in m["documentos"] if d["fragmentos"] == 1)}
    return salida


# ------------------------------------------------------------ 2. top-k por pregunta
def topk(b: Buscador) -> list[dict]:
    preguntas = json.loads((RAIZ / "evals" / "preguntas_pe3.json").read_text(encoding="utf-8"))["preguntas"]
    lectores = {d.codigo: set(d.roles) for d in leer_carpeta(RAIZ / "documentos")}
    filas = []
    for p in preguntas:
        top = b.buscar(p["pregunta"], p["usuario"], max(KS))
        rol = roles_de(p["usuario"])[0]
        fila = {"id": p["id"], "tipo": p["tipo"], "usuario": p["usuario"], "rol": rol,
                "top5": [f"{f['fragmento_id']} (§{','.join(f['secciones'])})" for f in top],
                "esperado": [f"{e['documento']} §{e['seccion']}" for e in p["esperado"]]}
        if p["esperado"]:
            puestos = [i for i, f in enumerate(top, 1) if acierta([f], p["esperado"])]
            fila["puesto_primer_acierto"] = puestos[0] if puestos else None
            for k in KS:
                fila[f"acierto@{k}"] = acierta(top[:k], p["esperado"])
        else:
            for k in KS:
                fuera_de_rol = [f for f in top[:k] if rol not in lectores[f["documento"]]]
                restringido = p.get("documento_restringido")
                fila[f"acierto@{k}"] = not fuera_de_rol and not any(f["documento"] == restringido for f in top[:k])
            fila["puesto_primer_acierto"] = "—"
        filas.append(fila)
    return filas


# ------------------------------------------------------------ 3. matriz de seguridad
def matriz_seguridad(b: Buscador) -> dict:
    seg = json.loads((RAIZ / "evals" / "consultas_seguridad.json").read_text(encoding="utf-8"))["documentos"]
    lectores = {d.codigo: set(d.roles) for d in leer_carpeta(RAIZ / "documentos")}
    umbral = CONFIG_RAG["umbral_similitud"]
    CONFIG_RAG["umbral_similitud"] = 0.0  # que el prompt se arme siempre, para poder inspeccionarlo
    celdas = []
    try:
        for doc, grupos in seg.items():
            frase = next(c for c in grupos["directas"] if c.startswith("TESTIGO-"))
            for rol, usuario in USUARIO_DE_ROL.items():
                permitido = rol in lectores[doc]
                consultas = [(t, c) for t in ("directas", "parafraseadas") for c in grupos[t]]
                en_resultados = en_prompt = 0
                for _, c in consultas:
                    # sin permiso: se mira TODO lo que el rol puede recuperar (k=50); con permiso, el top 5 real
                    if any(f["documento"] == doc for f in b.buscar(c, usuario, k=5 if permitido else 50)):
                        en_resultados += 1
                    sim = ProveedorSimulado("rag_sin_evidencia")
                    responder_pregunta(c, usuario, sim, b)
                    texto = sim.ultimo_prompt.replace(c, "")
                    if frase in texto or f"] {doc} §" in texto:
                        en_prompt += 1
                celdas.append({"documento": doc, "rol": rol, "usuario": usuario, "permiso": permitido,
                               "consultas": len(consultas), "en_resultados": en_resultados, "en_prompt": en_prompt,
                               "correcto": (en_resultados > 0) if permitido else (en_resultados == 0 and en_prompt == 0)})
    finally:
        CONFIG_RAG["umbral_similitud"] = umbral
    sin_permiso = [c for c in celdas if not c["permiso"]]
    return {"celdas": celdas,
            "consultas_sin_permiso": sum(c["consultas"] for c in sin_permiso),
            "fugas_resultados": sum(c["en_resultados"] for c in sin_permiso),
            "fugas_prompt": sum(c["en_prompt"] for c in sin_permiso),
            "control_positivo": all(c["correcto"] for c in celdas if c["permiso"])}


# ------------------------------------------------------------ 4. casos nuevos
def casos_nuevos(carpeta: Path, b: Buscador, simulado: bool) -> dict | None:
    archivos = sorted((RAIZ / "consultas_nuevas").glob("2*.json"))
    casos = [json.loads(a.read_text(encoding="utf-8")) for a in archivos]
    if any(c["esperado"] == "A_CONFIRMAR_POR_QA" for c in casos):
        print("Casos nuevos: falta la clasificación de QA; no se corren.", file=sys.stderr)
        return None
    filas = []
    for a, c in zip(archivos, casos):
        r = responder(c["entrada"], "u_analista_qa", ProveedorSimulado("rag_valido") if simulado else None, b)
        _json(carpeta / "casos_nuevos" / f"caso_{a.stem}.json", json.loads(r.model_dump_json()))
        p = r.propuesta
        propuesto = (p.impacto_gxp.value if p and p.impacto_gxp else "requiere_humano" if p and p.requiere_humano
                     else "fuera_de_alcance" if p and p.fuera_de_alcance else r.error.error)
        esperado = c["esperado"]["impacto_gxp"] or "fuera_de_alcance"
        sesgo = (None if propuesto == esperado or propuesto not in NIVELES or esperado not in NIVELES
                 else "sobre" if NIVELES.index(propuesto) > NIVELES.index(esperado) else "sub")
        filas.append({"n": a.stem, "consulta": c["entrada"]["descripcion"][:70], "esperado": esperado,
                      "revalidacion_esperada": c["esperado"]["requiere_revalidacion"], "propuesto": propuesto,
                      "revalidacion_propuesta": p.requiere_revalidacion if p else None,
                      "coincide": propuesto == esperado, "sesgo": sesgo,
                      "fundamento": [f"{x.codigo} §{x.seccion}" for x in p.fundamento] if p else [],
                      "tokens_entrada": r.metricas.input_tokens if r.metricas else 0,
                      "costo_usd": r.metricas.cost if r.metricas else 0.0,
                      "latencia_ms": r.metricas.latencia_ms if r.metricas else 0, "ok": r.ok})
        print(f"CCAM {a.stem}: {propuesto} (QA: {esperado})", file=sys.stderr)
    return {"filas": filas, "coincidencias": sum(f["coincide"] for f in filas), "total": len(filas),
            "sobre": sum(f["sesgo"] == "sobre" for f in filas), "sub": sum(f["sesgo"] == "sub" for f in filas),
            "costo_promedio_usd": round(sum(f["costo_usd"] for f in filas) / len(filas), 6)}


# ------------------------------------------------------------ informe
def informe(d: dict) -> str:
    si = lambda x: "✓" if x else "✗"
    L = [f"# Correcciones de la devolución de la PE3 — {d['fecha']}", "",
         f"Corpus congelado: `{d['hash_corpus'][:16]}…` (coincide con evals/corpus_congelado.json: {si(d['corpus_coincide'])}).", "",
         "## M-1 · Fragmentado A y B", "", "| | A | B |", "|---|---|---|"]
    fa, fb = d["fragmentado"]["A"], d["fragmentado"]["B"]
    for clave, nombre in [("tope_tokens", "Tope (tokens)"), ("solapamiento", "Solapamiento"), ("fragmentos", "Fragmentos"),
                          ("tokens_min", "Tokens mín."), ("tokens_mediana", "Tokens mediana"), ("tokens_max", "Tokens máx."),
                          ("documentos_en_un_solo_fragmento", "Documentos en un solo fragmento")]:
        L.append(f"| {nombre} | {fa[clave]} | {fb[clave]} |")
    L += ["", f"Método (igual en A y B): {fa['metodo_corte']}. Solapamiento: {fa['solapamiento_detalle']}. Prefijo: {fa['prefijo']}.", "",
          "## M-2 · M-5 · Top-k por pregunta (configuración A, híbrida)", "",
          "| Id | Tipo | Rol | Esperado | Puesto | @3 | @5 | Top 5 |", "|---|---|---|---|---|---|---|---|"]
    for f in d["topk"]:
        L.append(f"| {f['id']} | {f['tipo']} | {f['rol']} | {', '.join(f['esperado']) or '—'} | {f['puesto_primer_acierto'] or '✗'} | "
                 f"{si(f['acierto@3'])} | {si(f['acierto@5'])} | {'; '.join(f['top5'])} |")
    m = d["seguridad"]
    roles = list(USUARIO_DE_ROL)
    L += ["", "## M-5 · M-6 · Matriz de seguridad", "",
          f"Consultas desde roles sin permiso: {m['consultas_sin_permiso']} · fugas en resultados: {m['fugas_resultados']} · "
          f"fugas en el prompt: {m['fugas_prompt']} · control positivo: {si(m['control_positivo'])}", "",
          "| Documento | " + " | ".join(roles) + " |", "|---|" + "---|" * len(roles)]
    for doc in dict.fromkeys(c["documento"] for c in m["celdas"]):
        celdas = {c["rol"]: c for c in m["celdas"] if c["documento"] == doc}
        L.append(f"| {doc} | " + " | ".join(
            (f"ve: en el top 5 en {celdas[r]['en_resultados']} de {celdas[r]['consultas']} {si(celdas[r]['correcto'])}"
             if celdas[r]["permiso"] else
             f"bloqueado: {celdas[r]['en_resultados'] + celdas[r]['en_prompt']} fugas en {celdas[r]['consultas']} {si(celdas[r]['correcto'])}")
            for r in roles) + " |")
    if d.get("casos_nuevos"):
        c = d["casos_nuevos"]
        L += ["", "## M-4 · Casos nuevos con el corpus congelado", "",
              f"Coincidencia con QA: {c['coincidencias']}/{c['total']} · sobreclasifica {c['sobre']} · subclasifica {c['sub']} · "
              f"USD {c['costo_promedio_usd']:.6f} por CCAM", "",
              "| # | Caso | QA | Sistema | Revalidación QA/sistema | Fundamento |", "|---|---|---|---|---|---|"]
        for f in c["filas"]:
            L.append(f"| {f['n']} | {f['consulta']} | {f['esperado']} | {f['propuesto']}{'' if f['coincide'] else ' ✗'} | "
                     f"{'sí' if f['revalidacion_esperada'] else 'no'}/{'sí' if f['revalidacion_propuesta'] else 'no'} | "
                     f"{', '.join(f['fundamento'])} |")
    L += ["", "## M-3 · Objeto completo de responder()", "", "Ver `ejemplo_responder.json`."]
    return "\n".join(L) + "\n"


def correr(simulado: bool = False, destino: Path | None = None) -> Path:
    congelado = json.loads((RAIZ / "evals" / "corpus_congelado.json").read_text(encoding="utf-8"))
    actual, _ = hash_corpus()
    if actual != congelado["sha256_corpus"]:
        raise SystemExit(f"El corpus cambió desde que se congeló ({actual[:12]} ≠ {congelado['sha256_corpus'][:12]}): "
                         "la medición con casos nuevos no vale.")
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    carpeta = destino or (RAIZ / "resultados" / f"corrida_correcciones_pe3_{fecha}")
    carpeta.mkdir(parents=True, exist_ok=False)
    embedder = crear_embedder(True if simulado else None)
    base = carpeta / "_chroma" if destino else None
    buscadores = {}
    for config in ("A", "B"):
        col = ingestar(RAIZ / "documentos", config, destino=(base / config) if base else None, embedder=embedder,
                       manifiesto=carpeta / f"ingesta_{config}.json")
        buscadores[config] = Buscador(config, coleccion=col, embedder=embedder)
    b = buscadores[CONFIG_RAG["configuracion_vigente"]]

    datos = {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "hash_corpus": actual, "corpus_coincide": True,
             "fragmentado": fragmentado(carpeta), "topk": topk(b), "seguridad": matriz_seguridad(b),
             "casos_nuevos": casos_nuevos(carpeta, b, simulado)}
    entrada08 = json.loads((RAIZ / "consultas" / "08_audit_trail.json").read_text(encoding="utf-8"))["entrada"]
    ejemplo = responder(entrada08, "u_analista_qa", ProveedorSimulado("rag_valido") if simulado else None, b)
    _json(carpeta / "ejemplo_responder.json", json.loads(ejemplo.model_dump_json()))
    _json(carpeta / "medicion.json", datos)
    (carpeta / "medicion.md").write_text(informe(datos), encoding="utf-8")

    archivos = sorted(f for f in carpeta.rglob("*") if f.is_file() and "_chroma" not in f.parts and f.name != "manifiesto.json")
    _json(carpeta / "manifiesto.json", {
        "corrida": carpeta.name, "fecha": datetime.now().isoformat(timespec="seconds"),
        "modo": "simulado" if simulado else "real", "embeddings": embedder.nombre, "sha256_corpus": actual,
        "version_prompt": version_prompt_rag(), "commit": commit_actual(),
        "archivos": {str(f.relative_to(carpeta)).replace("\\", "/"): sha256(f) for f in archivos}})
    print(informe(datos))
    return carpeta


def main() -> int:
    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser(description="Corrida de las correcciones de la devolución de la PE3.")
    p.add_argument("--simulado", action="store_true", help="sin clave ni descarga")
    correr(p.parse_args().simulado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
