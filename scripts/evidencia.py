"""Junta la evidencia de terminal que pide el PDF de la PE2.

QUÉ HACE
    Corre el motor en cuatro situaciones y guarda lo que imprime la terminal,
    tal cual, en resultados/evidencia_*.txt:

    1. exito.txt          un CCAM real contra Claude (requiere ANTHROPIC_API_KEY en .env)
    2. reintento.txt      una salida inválida forzada (simulador): campo que falló,
                          reintento y error estructurado
    3. error_api.txt      una llamada REAL a Anthropic con una clave inválida:
                          el error de API capturado y traducido
    4. entrada.txt        una entrada inválida: se rechaza sin llamar al modelo

USO
    python -m scripts.evidencia
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "resultados"

CASOS = [
    ("exito", ["consultas/01_version_software.json"], {}),
    ("reintento", ["consultas/01_version_software.json", "--simulado", "invalido"], {}),
    ("error_api", ["consultas/01_version_software.json"],
     {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-ant-clave-invalida-de-prueba"}),
    ("entrada", ["consultas/extra/entrada_invalida.json", "--simulado", "valido"], {}),
]


def main() -> int:
    DESTINO.mkdir(exist_ok=True)
    for nombre, argumentos, variables in CASOS:
        entorno = {**os.environ, **variables, "PYTHONIOENCODING": "utf-8"}
        comando = [sys.executable, "-m", "src.motor", *argumentos]
        r = subprocess.run(comando, cwd=RAIZ, env=entorno, capture_output=True, text=True, encoding="utf-8")
        mostrado = "$ python -m src.motor " + " ".join(argumentos)
        texto = f"{mostrado}\n{r.stderr}{r.stdout}"
        (DESTINO / f"evidencia_{nombre}.txt").write_text(texto, encoding="utf-8")
        ultima = (r.stderr.strip().splitlines() or ["(sin salida)"])[-1]
        print(f"{nombre:<10} -> {ultima}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
