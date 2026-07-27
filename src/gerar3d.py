#!/usr/bin/env python3
"""Gera um modelo 3D a partir de UMA imagem (o "nosso Meshy" local, roda na GPU).

Backend padrao: TripoSR (leve). Salva o resultado em .obj (bom pro Mixamo) e .glb
(bom pro Blender). Roda no ambiente venv3d criado pelo instalar_3d.bat.

ATENCAO (honesto): so foi validado o "esqueleto" desta orquestracao; o passo do
TripoSR depende da instalacao com GPU (testar em casa). Se algo falhar, a mensagem
de erro do TripoSR aparece na tela para ajustarmos.

Uso (dentro do venv3d):
    venv3d\\Scripts\\python src/gerar3d.py --input input/personagem.png --out input/personagem
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_triposr(image: Path, out_dir: Path, triposr_dir: Path, python_exe: str) -> Path:
    """Chama o run.py do TripoSR e devolve o caminho do mesh gerado."""
    run_py = triposr_dir / "run.py"
    if not run_py.is_file():
        raise SystemExit(
            f"[gerar3d] TripoSR nao encontrado em {triposr_dir}.\n"
            "  Rode o instalar_3d.bat primeiro (ele clona o TripoSR)."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        python_exe, str(run_py), str(image.resolve()),
        "--output-dir", str(out_dir.resolve()),
        "--model-save-format", "obj",
    ]
    print(f"[gerar3d] TripoSR: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(triposr_dir))

    meshes = sorted(out_dir.rglob("mesh.obj")) or sorted(out_dir.rglob("*.obj"))
    if not meshes:
        raise SystemExit(f"[gerar3d] TripoSR rodou mas nao achei o mesh em {out_dir}")
    return meshes[0]


def _export_formats(mesh_path: Path, out_base: Path) -> None:
    """Converte o mesh gerado para .obj e .glb ao lado de out_base."""
    try:
        import trimesh
    except ImportError:
        raise SystemExit("[gerar3d] falta 'trimesh' (instale no venv3d).")

    scene = trimesh.load(str(mesh_path))
    obj_out = out_base.with_suffix(".obj")
    glb_out = out_base.with_suffix(".glb")
    scene.export(str(obj_out))
    scene.export(str(glb_out))
    print(f"[gerar3d] salvo: {obj_out.name} (p/ Mixamo) e {glb_out.name} (p/ Blender)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Imagem -> modelo 3D (gerador local).")
    ap.add_argument("--input", required=True, type=Path, help="imagem PNG/JPG do personagem")
    ap.add_argument("--out", required=True, type=Path, help="caminho base de saida (sem extensao)")
    ap.add_argument("--backend", default="triposr", choices=["triposr"], help="motor imagem->3D")
    ap.add_argument("--triposr-dir", type=Path, default=ROOT / "third_party" / "TripoSR")
    ap.add_argument("--python", default=sys.executable, help="python do venv3d")
    args = ap.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"[gerar3d] imagem nao encontrada: {args.input}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        if args.backend == "triposr":
            mesh = _run_triposr(args.input, tmp_dir, args.triposr_dir, args.python)
        else:
            raise SystemExit(f"[gerar3d] backend nao suportado: {args.backend}")
        _export_formats(mesh, args.out)

    print("\n[gerar3d] PRONTO! Proximo passo: rig + animacoes no Mixamo (use o .obj).")


if __name__ == "__main__":
    main()
