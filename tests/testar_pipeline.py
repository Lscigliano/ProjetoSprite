#!/usr/bin/env python3
"""Teste de fumaca do pipeline (NAO precisa de GPU).

Baixa um modelo 3D animado CC0 (o "Fox" do Khronos, dominio publico, sem login)
e roda o criar.py de ponta a ponta, conferindo que a folha, o JSON e o .tres do
Godot sao gerados com as 8 direcoes. Usa o modulo bpy (pip install bpy) + Workbench.

    py tests/testar_pipeline.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOX = ROOT / "work" / "_test_Fox.glb"
FOX_URL = ("https://raw.githubusercontent.com/KhronosGroup/"
           "glTF-Sample-Assets/main/Models/Fox/glTF-Binary/Fox.glb")


def main() -> None:
    FOX.parent.mkdir(parents=True, exist_ok=True)
    if not FOX.exists():
        print(f"[teste] baixando modelo CC0: {FOX_URL}")
        urllib.request.urlretrieve(FOX_URL, FOX)

    print("[teste] rodando criar.py de ponta a ponta...")
    subprocess.run(
        [sys.executable, str(ROOT / "criar.py"), str(FOX),
         "--name", "_smoketest", "--resolution", "192", "--engine", "BLENDER_WORKBENCH"],
        check=True,
    )

    png = ROOT / "output" / "_smoketest.png"
    meta = ROOT / "output" / "_smoketest.json"
    tres = ROOT / "output" / "_smoketest_frames.tres"
    for f in (png, meta, tres):
        assert f.exists(), f"saida faltando: {f}"

    data = json.loads(meta.read_text(encoding="utf-8"))
    dirs = data["animations"]["walk"]
    assert len(dirs) == 8, f"esperava 8 direcoes, veio {len(dirs)}"
    total = sum(d["frames"] for d in dirs.values())
    print(f"[teste] OK! folha={png.name}, 8 direcoes, {total} frames, .tres do Godot gerado.")


if __name__ == "__main__":
    main()
