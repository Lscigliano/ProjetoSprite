#!/usr/bin/env python3
"""CRIADOR SPRITES -- comando unico.

Simples assim:

    # a partir de um modelo 3D (precisa do Blender instalado):
    py criar.py input/hero.glb

    # a partir de frames ja renderizados (nao precisa do Blender):
    py criar.py work/hero/render --name hero

Ele faz tudo sozinho: render das 8 direcoes -> pixeliza -> espelha diagonais
-> monta o spritesheet + JSON -> gera o recurso do Godot (.tres).

Saida final em: output/<nome>.png, output/<nome>.json, output/<nome>_frames.tres
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# permite importar os modulos de src/
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image  # noqa: E402
import pixelize as px  # noqa: E402
import pack_spritesheet as packer  # noqa: E402
import godot_export as godot  # noqa: E402

MODEL_EXTS = {".glb", ".gltf", ".fbx", ".obj"}


def find_blender(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    on_path = shutil.which("blender")
    if on_path:
        return on_path
    # caminhos comuns no Windows
    base = Path(r"C:/Program Files/Blender Foundation")
    if base.is_dir():
        for d in sorted(base.iterdir(), reverse=True):
            exe = d / "blender.exe"
            if exe.is_file():
                return str(exe)
    return None


def _has_bpy() -> bool:
    import importlib.util
    return importlib.util.find_spec("bpy") is not None


def run_render(model: Path, out_dir: Path, config_path: Path, resolution: int,
               engine: str | None = None, blender: str | None = None) -> None:
    render_script = ROOT / "src" / "render_directions.py"
    base = ["--model", str(model), "--out", str(out_dir),
            "--config", str(config_path), "--resolution", str(resolution)]
    if engine:
        base += ["--engine", engine]

    if _has_bpy():
        # Blender como MODULO Python (pip install bpy): nao precisa do app,
        # nem de admin -- roda mesmo em maquina com AppLocker.
        cmd = [sys.executable, str(render_script)] + base
        print("[criar] render via modulo bpy (pip install bpy)")
    else:
        exe = find_blender(blender)
        if not exe:
            print(
                "\n[criar] ERRO: nem o modulo 'bpy' nem o Blender.exe foram encontrados.\n"
                "  Opcao A (recomendada): py -m pip install bpy\n"
                "  Opcao B: instale o Blender e passe --blender \"C:/.../blender.exe\".",
                file=sys.stderr,
            )
            sys.exit(2)
        cmd = [exe, "--background", "--python", str(render_script), "--"] + base
        print(f"[criar] render via Blender.exe: {exe}")
    subprocess.run(cmd, check=True)


def prepare_frames(render_dir: Path, frames_dir: Path, config: dict) -> None:
    """Pixeliza (ou copia) os frames renderizados para frames_dir."""
    pcfg = config.get("pixelize", {})
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    if pcfg.get("enabled", True):
        n = px.process_path(
            render_dir, frames_dir,
            height=pcfg.get("target_height", 64),
            colors=pcfg.get("colors", 0),
            alpha_threshold=pcfg.get("alpha_threshold", 128),
        )
        print(f"[criar] pixelizados {n} frames -> {frames_dir}")
    else:
        shutil.copytree(render_dir, frames_dir)
        print(f"[criar] copiados frames -> {frames_dir}")


def mirror_directions(frames_dir: Path, config: dict) -> None:
    """Cria as direcoes espelhadas (ex.: NW a partir de NE) por flip horizontal."""
    created = 0
    for anim in config["animations"]:
        anim_dir = frames_dir / anim["name"]
        if not anim_dir.is_dir():
            continue
        for d in config["directions"]:
            src_name = d.get("mirror_of")
            if not src_name:
                continue
            src = anim_dir / src_name
            dst = anim_dir / d["name"]
            if dst.exists() or not src.is_dir():
                continue
            dst.mkdir(parents=True, exist_ok=True)
            for f in sorted(src.glob("*.png")):
                with Image.open(f) as im:
                    im.convert("RGBA").transpose(Image.FLIP_LEFT_RIGHT).save(dst / f.name)
                created += 1
    if created:
        print(f"[criar] {created} frames espelhados (diagonais/lado esquerdo)")


def main() -> None:
    ap = argparse.ArgumentParser(description="CRIADOR SPRITES - gera spritesheet isometrico 8-direcoes.")
    ap.add_argument("entrada", type=Path, help="modelo 3D (.glb/.fbx/.obj) OU pasta de frames ja renderizados")
    ap.add_argument("--name", default=None, help="nome do personagem (padrao: nome do arquivo/pasta)")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "default.json")
    ap.add_argument("--blender", default=None, help="caminho do blender.exe (se nao estiver no PATH)")
    ap.add_argument("--resolution", type=int, default=512, help="resolucao do render antes de pixelizar")
    ap.add_argument("--engine", default=None, help="motor Blender (EEVEE/CYCLES/WORKBENCH); auto se vazio")
    ap.add_argument("--image-res", default=None, help='caminho da imagem no Godot (ex.: "res://sprites/hero.png")')
    args = ap.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    entrada = args.entrada
    name = args.name or entrada.stem
    work = ROOT / "work" / name
    out_base = ROOT / "output" / name

    # 1. obter os frames renderizados (nas direcoes nao-espelhadas)
    if entrada.is_file() and entrada.suffix.lower() in MODEL_EXTS:
        render_dir = work / "render"
        run_render(entrada, render_dir, args.config, args.resolution, args.engine, args.blender)
    elif entrada.is_dir():
        render_dir = entrada
        print(f"[criar] usando frames existentes de {render_dir} (sem Blender)")
    else:
        print(f"[criar] ERRO: entrada invalida: {entrada}", file=sys.stderr)
        sys.exit(2)

    # 2. pixelizar
    frames_dir = work / "frames"
    prepare_frames(render_dir, frames_dir, config)

    # 3. espelhar as diagonais/lado esquerdo
    mirror_directions(frames_dir, config)

    # 4. montar o spritesheet + JSON
    out_base.parent.mkdir(parents=True, exist_ok=True)
    packer.pack(frames_dir, out_base, config)

    # 5. gerar o recurso do Godot
    meta = json.loads(out_base.with_suffix(".json").read_text(encoding="utf-8"))
    image_res = args.image_res or f'res://{meta["image"]}'
    tres = godot.build_tres(meta, image_res)
    tres_path = out_base.parent / f"{name}_frames.tres"
    tres_path.write_text(tres, encoding="utf-8")

    print("\n[criar] PRONTO!")
    print(f"  folha:  {out_base.with_suffix('.png')}")
    print(f"  json:   {out_base.with_suffix('.json')}")
    print(f"  godot:  {tres_path}")


if __name__ == "__main__":
    main()
