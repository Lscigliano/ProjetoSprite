#!/usr/bin/env python3
"""Verifica o que ja esta pronto na maquina para cada FASE do pipeline.

Roda no Python base (nao no venv3d). Nao instala nada -- so diagnostica e diz
o que falta. Util ao chegar na maquina de casa.

    py verificar_ambiente.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def has(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def check_venv3d_torch():
    py = ROOT / "venv3d" / "Scripts" / "python.exe"
    if not py.exists():
        return False, "venv3d nao criado (rode instalar_3d.bat)"
    try:
        out = subprocess.run(
            [str(py), "-c",
             "import torch;print(torch.cuda.is_available(),"
             "torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"],
            capture_output=True, text=True, timeout=90,
        )
        s = (out.stdout or "").strip()
        if s.startswith("True"):
            return True, f"CUDA OK ({s.split(maxsplit=1)[-1] or 'GPU'})"
        return False, f"torch sem CUDA: {s or (out.stderr or '').strip()[:80]}"
    except Exception as e:  # noqa: BLE001
        return False, f"erro ao checar torch: {e}"


def main() -> None:
    print("== CRIADOR SPRITES - verificacao de ambiente ==\n")
    print(f"Python base: {sys.version.split()[0]}\n")

    triposr = (ROOT / "third_party" / "TripoSR" / "run.py").exists()
    unirig = (ROOT / "third_party" / "UniRig" / "run.py").exists()
    torch_ok, torch_msg = check_venv3d_torch()

    checks = [
        ("Pillow (montar folha)", has("PIL")),
        ("numpy", has("numpy")),
        ("trimesh (I/O 3D)", has("trimesh")),
        ("bpy (render Blender via pip)", has("bpy")),
        (f"venv3d + PyTorch CUDA  ->  {torch_msg}", torch_ok),
        ("TripoSR (imagem->3D)", triposr),
        ("UniRig (rig)", unirig),
    ]
    for name, ok in checks:
        print(f"  [{'OK   ' if ok else 'FALTA'}] {name}")

    # Fase 4-5 (render + folha + Godot) usa PIL + bpy; trimesh so nas fases 3D.
    base_ok = has("PIL") and has("bpy")
    print("\nStatus das fases:")
    print(f"  Fase 4-5 (render 8 dir + folha + Godot): "
          f"{'PRONTA' if base_ok else 'faltam deps -> py -m pip install -r requirements.txt'}")
    print(f"  Fase 2 (imagem->3D): "
          f"{'PRONTA' if (torch_ok and triposr) else 'pendente -> instalar_3d.bat (precisa de GPU)'}")
    print(f"  Fase 3 (rig + animacoes): "
          f"{'PRONTA' if (torch_ok and unirig) else 'pendente -> instalar UniRig (precisa de GPU)'}")


if __name__ == "__main__":
    main()
