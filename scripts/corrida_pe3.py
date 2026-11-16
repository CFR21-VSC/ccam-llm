"""Corrida única de la PE3: recuperación, permisos, preguntas y CCAM con RAG, en una sola carpeta.

QUÉ HACE (en este orden, una vez cada cosa)
    1. Ingesta de las dos configuraciones de fragmentado (A ~400 tokens, B ~1.000).
    2. Recall@3 y Recall@5 de vectorial, BM25 e híbrida, en A y en B.
    3. Tabla de consultas donde la híbrida acierta y la vectorial falla.
    4. Evidencia de permisos: qué documentos ve cada rol y que las frases testigo
       no llegan a quien no tiene permiso (ni en resultados ni en el prompt).
    5. Las 10 preguntas de evals/preguntas_pe3.json respondidas con el modelo.
    6. Los 15 CCAM de consultas/ por responder() con u_analista_qa, comparados con la PE2.
    7. manifiesto.json con modo, versión de prompt, commit y hash de cada archivo.

    resultados/corrida_pe3_AAAAMMDD_HHMM/
        ingesta_A.json, ingesta_B.json      manifiestos de ingesta
        recuperacion.json / .md             Recall@k y híbrida contra vectorial
        permisos.json                       visibilidad por rol y frases testigo
        preguntas/P01.json ... P10.json     respuesta completa de cada pregunta
        ccam/caso_NN.json                   respuesta completa de cada CCAM
        medicion.json / medicion.md         todo lo anterior en tablas, leído de los archivos
        manifiesto.json

USO
    python -m scripts.corrida_pe3                       # modelo real (.env) y embeddings locales
    python -m scripts.corrida_pe3 --simulado rag_valido --embeddings-simulados   # sin clave ni descarga (CI)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scripts.corrida import armar_medicion, casos_a_correr, commit_actual, medicion_md, sha256
from src.proveedores import ProveedorSimulado
from src.rag.buscar import Buscador, USUARIOS, roles_de
from src.rag.corpus import leer_carpeta
from src.rag.embeddings import crear_embedder
from src.rag.ingestar import CONFIG_RAG, RAIZ, ingestar
from src.rag.responder import responder, responder_pregunta, version_prompt_rag

TESTIGOS = {"INF-AUD-2026-03": "TESTIGO-AUD-7731", "EXP-VAL-CROM-01": "TESTIGO-VAL-4408",
            "HAL-INSP-2026-01": "TESTIGO-INSP-2290"}
CORRIDA_PE2 = RAIZ / "resultados" / "corrida_20261116_1116" / "medicion.json"
KS = (3, 5)
METODOS = ("vectorial", "bm25", "hibrida")


def _json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def acierta(fragmentos: list[dict], esperado: list[dict]) -> bool:
    """Acierto = algún fragmento es del documento esperado Y contiene la sección esperada."""
    return any(f["documento"] == e["documento"] and e["seccion"] in f["secciones"]
               for f in fragmentos for e in esperado)


def resultados_de(b: Buscador, metodo: str, consulta: str, usuario: str, k: int) -> list[dict]:
    roles = roles_de(usuario)
    if metodo == "vectorial":
        return b.buscar_vectorial(consulta, roles, k)
    if metodo == "bm25":
        return b.buscar_bm25(consulta, roles, k)
    return b.buscar(consulta, usuario, k)


# ------------------------------------------------------------ 2 y 3. recuperación
def medir_recuperacion(buscadores: dict[str, Buscador]) -> dict:
    preguntas = json.loads((RAIZ / "evals" / "preguntas_pe3.json").read_text(encoding="utf-8"))["preguntas"]
    codigos = json.loads((RAIZ / "evals" / "consultas_codigos.json").read_text(encoding="utf-8"))
    medibles = ([{"id": p["id"], "consulta": p["pregunta"], "usuario": p["usuario"], "esperado": p["esperado"],
                  "origen": "preguntas_pe3"} for p in preguntas if p["esperado"]] +
                [{"id": c["id"], "consulta": c["consulta"], "usuario": codigos["usuario"],
                  "esperado": c["esperado"], "origen": "consultas_codigos"} for c in codigos["consultas"]])
    salida: dict = {"consultas_medidas": len(medibles), "configuraciones": {}}
    for config, b in buscadores.items():
        filas = []
        for q in medibles:
            fila = {"id": q["id"], "origen": q["origen"], "consulta": q["consulta"], "esperado": q["esperado"]}
            for metodo in METODOS:
                top = resultados_de(b, metodo, q["consulta"], q["usuario"], max(KS))
                for k in KS:
                    fila[f"{metodo}@{k}"] = acierta(top[:k], q["esperado"])
                fila[f"{metodo}_top3"] = [f["fragmento_id"] for f in top[:3]]
            fila["tokens_contexto@5"] = sum(
                -(-len(f["texto"]) // 4) for f in resultados_de(b, "hibrida", q["consulta"], q["usuario"], 5))
            filas.append(fila)
        recall = {f"{m}@{k}": round(sum(f[f"{m}@{k}"] for f in filas) / len(filas), 4) for m in METODOS for k in KS}
        recall_preguntas = {f"{m}@{k}": round(sum(f[f"{m}@{k}"] for f in filas if f["origen"] == "preguntas_pe3")
                                              / sum(1 for f in filas if f["origen"] == "preguntas_pe3"), 4)
                            for m in METODOS for k in KS}
        salida["configuraciones"][config] = {
            **CONFIG_RAG["configuraciones"][config], "fragmentos": b.coleccion.count(),
            "recall": recall, "recall_solo_10_preguntas": recall_preguntas,
            "tokens_contexto_promedio@5": round(sum(f["tokens_contexto@5"] for f in filas) / len(filas)),
            "filas": filas,
            "hibrida_acierta_vectorial_falla@3": [f["id"] for f in filas if f["hibrida@3"] and not f["vectorial@3"]],
            "vectorial_acierta_hibrida_falla@3": [f["id"] for f in filas if f["vectorial@3"] and not f["hibrida@3"]],
        }
    return salida


# ------------------------------------------------------------ 4. permisos
def evidencia_permisos(b: Buscador) -> dict:
    documentos = {d.codigo: d.roles for d in leer_carpeta(RAIZ / "documentos")}
    visibles = {}
    for usuario in USUARIOS["usuarios"]:
        todo = b.buscar_vectorial("documento", roles_de(usuario))  # sin n: todo lo autorizado
        visibles[usuario] = sorted({f["documento"] for f in todo})
    testigos = []
    for doc, frase in TESTIGOS.items():
        for usuario, datos in USUARIOS["usuarios"].items():
            permitido = datos["rol"] in documentos[doc]
            resultados = b.buscar(frase, usuario, k=50)
            en_resultados = any(frase in f["texto"] for f in resultados)
            simulado = ProveedorSimulado("rag_sin_evidencia")
            umbral = CONFIG_RAG["umbral_similitud"]
            CONFIG_RAG["umbral_similitud"] = 0.0  # para que el prompt se arme y se pueda inspeccionar
            pregunta = f"¿Qué dice el documento con el código {frase}?"
            try:
                responder_pregunta(pregunta, usuario, simulado, b)
            finally:
                CONFIG_RAG["umbral_similitud"] = umbral
            # la pregunta misma contiene la frase: se mira solo lo que agregó el sistema (la evidencia)
            en_prompt = frase in simulado.ultimo_prompt.replace(pregunta, "")
            testigos.append({"documento": doc, "frase": frase, "usuario": usuario, "rol": datos["rol"],
                             "tiene_permiso": permitido, "en_resultados": en_resultados, "en_prompt": en_prompt,
                             "correcto": (en_resultados and en_prompt) if permitido
                             else (not en_resultados and not en_prompt)})
    desconocido = b.buscar("audit trail", "u_intruso", k=10)
    return {"visibles_por_usuario": visibles, "testigos": testigos,
            "testigos_correctos": f"{sum(t['correcto'] for t in testigos)}/{len(testigos)}",
            "usuario_desconocido_recibe": len(desconocido)}


# ------------------------------------------------------------ 5. preguntas
def correr_preguntas(carpeta: Path, b: Buscador, simulado: str | None, pausa: float) -> list[dict]:
    preguntas = json.loads((RAIZ / "evals" / "preguntas_pe3.json").read_text(encoding="utf-8"))["preguntas"]
    filas = []
    for p in preguntas:
        r = responder_pregunta(p["pregunta"], p["usuario"], ProveedorSimulado(simulado) if simulado else None,
                               b, pregunta_id=p["id"])
        _json(carpeta / "preguntas" / f"{p['id']}.json", json.loads(r.model_dump_json()))
        s = r.salida
        citas = [f"{c.codigo} §{c.seccion}" for c in s.citas] if s else []
        restringido = p.get("documento_restringido")
        fila = {
            "id": p["id"], "tipo": p["tipo"], "usuario": p["usuario"], "ok": r.ok,
            "requiere_humano": s.requiere_humano if s else None, "requiere_humano_esperado": p["requiere_humano"],
            "citas": citas, "esperado": [f"{e['documento']} §{e['seccion']}" for e in p["esperado"]],
            "cita_esperada": any(c.codigo == e["documento"] for c in (s.citas if s else []) for e in p["esperado"]),
            "evidencia_maxima": r.evidencia_maxima,
            "restringido_en_fuentes": any(f.documento == restringido for f in r.fuentes) if restringido else None,
            "tokens": (r.metricas.input_tokens, r.metricas.output_tokens) if r.metricas else (0, 0),
            "costo_usd": r.metricas.cost if r.metricas else 0.0,
            "latencia_ms": r.metricas.latencia_ms if r.metricas else 0,
            "error": r.error.error if r.error else None,
        }
        fila["correcta"] = r.ok and fila["requiere_humano"] == p["requiere_humano"] and (
            fila["cita_esperada"] if p["esperado"] else not citas) and not fila["restringido_en_fuentes"]
        filas.append(fila)
        print(f"Pregunta {p['id']}: {'OK' if fila['correcta'] else 'REVISAR'} "
              f"(requiere_humano={fila['requiere_humano']}, citas={citas})", file=sys.stderr)
        if not simulado:
            time.sleep(pausa)
    return filas


# ------------------------------------------------------------ 6. CCAM
def correr_ccam(carpeta: Path, b: Buscador, simulado: str | None, pausa: float) -> dict:
    casos, _ = casos_a_correr()
    destino = carpeta / "ccam"
    for archivo in casos:
        numero = archivo.name[:2]
        entrada = json.loads(archivo.read_text(encoding="utf-8"))["entrada"]
        r = responder(entrada, "u_analista_qa", ProveedorSimulado(simulado) if simulado else None, b)
        _json(destino / f"caso_{numero}.json", json.loads(r.model_dump_json()))
        nivel = (r.propuesta.impacto_gxp.value if r.propuesta and r.propuesta.impacto_gxp else
                 "requiere_humano" if r.propuesta and r.propuesta.requiere_humano else
                 "fuera_de_alcance" if r.propuesta and r.propuesta.fuera_de_alcance else r.error.error)
        print(f"CCAM {numero}: {nivel}", file=sys.stderr)
        if not simulado:
            time.sleep(pausa)
    med = armar_medicion(destino, casos)
    for fila in med["filas"]:  # requiere_humano no es un nivel: se muestra como tal
        r = json.loads((destino / f"caso_{fila['n']}.json").read_text(encoding="utf-8"))
        if (r.get("propuesta") or {}).get("requiere_humano"):
            fila["propuesto"] = "requiere_humano"
        fila["fuentes"] = sorted({f["documento"] for f in r.get("fuentes", [])})
        fila["fundamento"] = [f"{c['codigo']} §{c['seccion']}" for c in (r.get("propuesta") or {}).get("fundamento", [])]
    if CORRIDA_PE2.exists():
        pe2 = json.loads(CORRIDA_PE2.read_text(encoding="utf-8"))
        por_n = {f["n"]: f for f in pe2["filas"]}
        med["comparacion_pe2"] = {
            "corrida_pe2": CORRIDA_PE2.parent.name,
            "coincidencia_pe2": pe2["coincidencia_total"], "coincidencia_pe3": med["coincidencia_total"],
            "tokens_entrada_promedio_pe2": pe2["promedios"]["tokens_entrada"],
            "costo_promedio_pe2": pe2["promedios"]["costo_usd"],
            "latencia_promedio_pe2": pe2["promedios"]["latencia_ms"],
            "sesgo_pe2": pe2["sesgo"],
            "casos": [{"n": f["n"], "esperado": f["esperado"], "pe2": por_n.get(f["n"], {}).get("propuesto"),
                       "pe3": f["propuesto"]} for f in med["filas"]],
        }
    return med


# ------------------------------------------------------------ informe
def informe_md(rec: dict, perm: dict, preg: list[dict], med: dict, fecha: str, vigente: str) -> str:
    pct = lambda x: f"{x:.0%}"
    L = [f"# Corrida PE3 — {fecha}", "", "Todo sale de los archivos de esta carpeta.", "",
         "## 1. Recall@k por configuración de fragmentado", "",
         f"Consultas medidas: {rec['consultas_medidas']} (6 preguntas normales + 8 con códigos exactos). "
         "Acierto = el documento y la sección esperados están en los k primeros fragmentos.", "",
         "| Config | Fragmentos | Tokens de contexto @5 | Vectorial @3 | @5 | BM25 @3 | @5 | Híbrida @3 | @5 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for c, d in rec["configuraciones"].items():
        r = d["recall"]
        L.append(f"| {c} (~{d['max_tokens']} tokens) | {d['fragmentos']} | {d['tokens_contexto_promedio@5']} | "
                 f"{pct(r['vectorial@3'])} | {pct(r['vectorial@5'])} | {pct(r['bm25@3'])} | {pct(r['bm25@5'])} | "
                 f"{pct(r['hibrida@3'])} | {pct(r['hibrida@5'])} |")
    d = rec["configuraciones"][vigente]
    L += ["", f"## 2. Híbrida acierta y vectorial falla (config {vigente}, k = 3)", "",
          "| Id | Consulta | Esperado | Top 3 vectorial | Top 3 híbrida |", "|---|---|---|---|---|"]
    for f in d["filas"]:
        if f["id"] in d["hibrida_acierta_vectorial_falla@3"]:
            esp = ", ".join(f"{e['documento']} §{e['seccion']}" for e in f["esperado"])
            L.append(f"| {f['id']} | {f['consulta']} | {esp} | {', '.join(f['vectorial_top3'])} | "
                     f"{', '.join(f['hibrida_top3'])} |")
    L += ["", f"Al revés (vectorial acierta y la híbrida falla): {d['vectorial_acierta_hibrida_falla@3'] or 'ninguna'}.",
          "", "## 3. Permisos", "", "| Usuario | Documentos que ve |", "|---|---|"]
    for u, docs in perm["visibles_por_usuario"].items():
        L.append(f"| {u} | {len(docs)}: {', '.join(docs)} |")
    L += ["", f"Frases testigo: {perm['testigos_correctos']} combinaciones documento × usuario correctas "
          "(con permiso: aparece en resultados y prompt; sin permiso: en ninguno). "
          f"Usuario desconocido recibe {perm['usuario_desconocido_recibe']} fragmentos.", "",
          "| Documento | Frase | Usuario | ¿Permiso? | ¿En resultados? | ¿En prompt? |", "|---|---|---|---|---|---|"]
    for t in perm["testigos"]:
        si = lambda b: "Sí" if b else "No"
        L.append(f"| {t['documento']} | {t['frase']} | {t['usuario']} | {si(t['tiene_permiso'])} | "
                 f"{si(t['en_resultados'])} | {si(t['en_prompt'])} |")
    L += ["", "## 4. Las 10 preguntas", "",
          "| Id | Tipo | Usuario | requiere_humano (esperado) | Citas | Esperado | Similitud máx. | ¿Correcta? |",
          "|---|---|---|---|---|---|---|---|"]
    for p in preg:
        L.append(f"| {p['id']} | {p['tipo']} | {p['usuario']} | {p['requiere_humano']} ({p['requiere_humano_esperado']}) | "
                 f"{', '.join(p['citas']) or '-'} | {', '.join(p['esperado']) or '-'} | "
                 f"{p['evidencia_maxima'] if p['evidencia_maxima'] is not None else '-'} | {'Sí' if p['correcta'] else 'No'} |")
    L += ["", f"Correctas: {sum(p['correcta'] for p in preg)}/{len(preg)}.", "",
          "## 5. Los 15 CCAM con RAG (u_analista_qa)", "",
          medicion_md(med, fecha).split("\n", 2)[2].replace("cada fila es la ejecución de su `caso_NN.txt`",
                                                            "cada fila es el `ccam/caso_NN.json` de su ejecución")]
    if "comparacion_pe2" in med:
        c = med["comparacion_pe2"]
        L += ["## 6. PE2 (catálogo) contra PE3 (RAG)", "",
              f"| | PE2 ({c['corrida_pe2']}) | PE3 |", "|---|---|---|",
              f"| Coincidencia con QA | {c['coincidencia_pe2']['aciertos']}/{c['coincidencia_pe2']['total']} | "
              f"{c['coincidencia_pe3']['aciertos']}/{c['coincidencia_pe3']['total']} |",
              f"| Tokens de entrada promedio | {c['tokens_entrada_promedio_pe2']} | {med['promedios']['tokens_entrada']} |",
              f"| Costo promedio USD | {c['costo_promedio_pe2']:.6f} | {med['promedios']['costo_usd']:.6f} |",
              f"| Latencia promedio ms | {c['latencia_promedio_pe2']} | {med['promedios']['latencia_ms']} |",
              f"| Sobre / subclasificaciones | {c['sesgo_pe2']['sobreclasifica']} / {c['sesgo_pe2']['subclasifica']} | "
              f"{med['sesgo']['sobreclasifica']} / {med['sesgo']['subclasifica']} |", "",
              "| # | Esperado QA | PE2 | PE3 |", "|---|---|---|---|",
              *[f"| {x['n']} | {x['esperado']} | {x['pe2']} | {x['pe3']} |" for x in c["casos"]]]
    return "\n".join(L) + "\n"


def correr(simulado: str | None = None, embeddings_simulados: bool = False, pausa: float = 1.0,
           destino: Path | None = None) -> Path:
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    carpeta = destino or (RAIZ / "resultados" / f"corrida_pe3_{fecha}")
    carpeta.mkdir(parents=True, exist_ok=False)
    embedder = crear_embedder(True if embeddings_simulados else None)
    base = carpeta / "_chroma" if destino else None  # en pruebas, la base queda dentro de la carpeta temporal

    buscadores = {}
    for config in CONFIG_RAG["configuraciones"]:
        col = ingestar(RAIZ / "documentos", config, destino=(base / config) if base else None,
                       embedder=embedder, manifiesto=carpeta / f"ingesta_{config}.json")
        buscadores[config] = Buscador(config, coleccion=col, embedder=embedder)
        print(f"Ingesta {config}: {col.count()} fragmentos", file=sys.stderr)
    vigente = CONFIG_RAG["configuracion_vigente"]
    b = buscadores[vigente]

    rec = medir_recuperacion(buscadores)
    _json(carpeta / "recuperacion.json", rec)
    perm = evidencia_permisos(b)
    _json(carpeta / "permisos.json", perm)
    preg = correr_preguntas(carpeta, b, simulado, pausa)
    med = correr_ccam(carpeta, b, simulado, pausa)

    todo = {"configuracion_vigente": vigente, "recuperacion": {c: {k: v for k, v in d.items() if k != "filas"}
                                                               for c, d in rec["configuraciones"].items()},
            "permisos": {k: v for k, v in perm.items() if k != "testigos"}, "preguntas": preg, "ccam": med}
    _json(carpeta / "medicion.json", todo)
    texto = informe_md(rec, perm, preg, med, datetime.now().strftime("%Y-%m-%d %H:%M"), vigente)
    (carpeta / "medicion.md").write_text(texto, encoding="utf-8")

    archivos = sorted(f for f in carpeta.rglob("*") if f.is_file() and "_chroma" not in f.parts
                      and f.name != "manifiesto.json")
    _json(carpeta / "manifiesto.json", {
        "corrida": carpeta.name, "fecha": datetime.now().isoformat(timespec="seconds"),
        "modo": f"simulado:{simulado}" if simulado else "real", "modelo": med.get("modelo"),
        "embeddings": embedder.nombre, "configuracion_vigente": vigente,
        "version_prompt": version_prompt_rag(), "commit": commit_actual(),
        "archivos": {str(f.relative_to(carpeta)).replace("\\", "/"): sha256(f) for f in archivos}})
    print(texto)
    mostrar = carpeta.relative_to(RAIZ) if carpeta.is_relative_to(RAIZ) else carpeta
    print(f"Corrida guardada en {mostrar}", file=sys.stderr)
    return carpeta


def main() -> int:
    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser(description="Corrida única de la PE3 (RAG).")
    p.add_argument("--simulado", metavar="ESCENARIO", help="rag_valido | rag_sin_evidencia (sin clave)")
    p.add_argument("--embeddings-simulados", action="store_true", help="sin descargar el modelo (CI)")
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args()
    correr(a.simulado, a.embeddings_simulados, a.pausa)
    return 0


if __name__ == "__main__":
    sys.exit(main())
