#!/usr/bin/env python3
"""CRIADOR SPRITES -- comando unico (estilo "PixelLab caseiro").

A entrada pode ser 4 coisas -- o programa detecta e roda as fases certas:

    # 1) TEXTO (descreva o personagem)  [Fase 1: SD local -> imagem]
    py criar.py "urso guerreiro chibi, armadura laranja, olhos vermelhos" --size 64

    # 2) IMAGEM (voce ja tem o desenho)  [pula a Fase 1]
    py criar.py input/arqueiro.png --size 64

    # 3) MODELO 3D animado (.glb/.fbx/.obj)  [pula 1-3]
    py criar.py input/hero.glb

    # 4) FRAMES ja renderizados (pasta)  [so monta a folha]
    py criar.py work/hero/render --name hero

Fases: (1) texto->imagem [SD]  (2) imagem->3D [TripoSR]  (3) rig+animacoes [UniRig]
       (4) render 8 direcoes [bpy]  (5) pixeliza -> folha -> Godot.

As fases 1-3 precisam da GPU (venv3d, criado pelo instalar_3d.bat). As fases 4-5
rodam em qualquer maquina. Saida: output/<nome>.png / .json / _frames.tres (Godot 4).
"""
from __future__ import annotations

import argparse
import json
import os
import re
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
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


# ----------------------------------------------------------------------------
# helpers de ambiente
# ----------------------------------------------------------------------------
def find_blender(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    on_path = shutil.which("blender")
    if on_path:
        return on_path
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


def venv3d_python() -> Path | None:
    p = ROOT / "venv3d" / "Scripts" / "python.exe"
    return p if p.exists() else None


def venv_bpy_python() -> Path | None:
    p = ROOT / "venv_bpy" / "Scripts" / "python.exe"
    return p if p.exists() else None


def _erro_gpu(fase: str) -> None:
    print(
        f"\n[criar] A fase '{fase}' precisa da GPU (ambiente venv3d), que nao existe aqui.\n"
        "  -> Rode em casa (maquina com NVIDIA): instalar_3d.bat\n"
        "  -> Ou forneca a entrada ja pronta: uma IMAGEM, um MODELO .glb ou uma pasta de FRAMES.\n"
        "  (Use 'py verificar_ambiente.py' para ver o que esta pronto.)",
        file=sys.stderr,
    )
    sys.exit(3)


# ----------------------------------------------------------------------------
# fases generativas (rodam no venv3d / GPU)
# ----------------------------------------------------------------------------
def run_concept(prompt: str, out_image: Path, size: int) -> None:
    py = venv3d_python()
    if not py:
        _erro_gpu("1: texto -> imagem (Stable Diffusion)")
    out_image.parent.mkdir(parents=True, exist_ok=True)
    print(f"[criar] Fase 1: texto -> pixelart (SD) -> {out_image.name}")
    subprocess.run(
        [str(py), str(ROOT / "src" / "gerar_concept.py"),
         "--prompt", prompt, "--out", str(out_image), "--size", str(size)],
        check=True,
    )


def run_gerar3d(image: Path, out_glb: Path) -> None:
    py = venv3d_python()
    if not py:
        _erro_gpu("2: imagem -> 3D (TripoSR)")
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    print(f"[criar] Fase 2: imagem -> 3D -> {out_glb.name}")
    subprocess.run(
        [str(py), str(ROOT / "src" / "gerar3d.py"),
         "--input", str(image), "--out", str(out_glb.with_suffix(""))],
        check=True,
    )


def run_rig(model_in: Path, out_glb: Path, config_path: Path) -> None:
    # rig.py usa bpy (rig manual + skin + animacoes), nao GPU/torch -> roda no venv_bpy,
    # nao no venv3d (que so tem torch/TripoSR, sem bpy: wheel de bpy so existe p/ Python 3.13).
    py = venv_bpy_python()
    if not py:
        raise SystemExit(
            "\n[criar] A fase '3: rig + animacoes' precisa do venv_bpy (Python 3.13 + bpy), que nao existe aqui.\n"
            "  -> py -3.13 -m venv venv_bpy && venv_bpy\\Scripts\\python -m pip install -r requirements.txt"
        )
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    print(f"[criar] Fase 3: rig + animacoes -> {out_glb.name}")
    subprocess.run(
        [str(py), str(ROOT / "src" / "rig.py"),
         "--input", str(model_in), "--out", str(out_glb), "--config", str(config_path)],
        check=True,
    )


# ----------------------------------------------------------------------------
# fase 4: render (bpy) -- roda em qualquer maquina
# ----------------------------------------------------------------------------
def run_render(model: Path, out_dir: Path, config_path: Path, resolution: int,
               engine: str | None = None, blender: str | None = None,
               elevation: float | None = None) -> None:
    render_script = ROOT / "src" / "render_directions.py"
    base = ["--model", str(model), "--out", str(out_dir),
            "--config", str(config_path), "--resolution", str(resolution)]
    if engine:
        base += ["--engine", engine]
    if elevation is not None:
        base += ["--elevation", str(elevation)]

    if _has_bpy():
        cmd = [sys.executable, str(render_script)] + base
        print("[criar] Fase 4: render via modulo bpy (pip install bpy)")
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
        print(f"[criar] Fase 4: render via Blender.exe: {exe}")
    subprocess.run(cmd, check=True)


# ----------------------------------------------------------------------------
# fase 5: pixeliza / espelha / monta folha / Godot -- roda em qualquer maquina
# ----------------------------------------------------------------------------
def prepare_frames(render_dir: Path, frames_dir: Path, config: dict) -> None:
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
        print(f"[criar] Fase 5: pixelizados {n} frames -> {frames_dir}")
    else:
        shutil.copytree(render_dir, frames_dir)
        print(f"[criar] Fase 5: copiados frames -> {frames_dir}")


def mirror_directions(frames_dir: Path, config: dict) -> None:
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


# ----------------------------------------------------------------------------
def _slug(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    return "_".join(words[:3]) or "personagem"


def classify(raw: str) -> str:
    p = Path(raw)
    if p.is_dir():
        return "frames"
    if p.is_file():
        ext = p.suffix.lower()
        if ext in MODEL_EXTS:
            return "model"
        if ext in IMAGE_EXTS:
            return "image"
        return "arquivo_desconhecido"
    return "text"  # nao e um caminho existente -> tratamos como descricao (prompt)


def main() -> None:
    ap = argparse.ArgumentParser(description="CRIADOR SPRITES - texto/imagem/modelo -> spritesheet 8 direcoes.")
    ap.add_argument("entrada", help='TEXTO (descricao) OU imagem OU modelo 3D OU pasta de frames')
    ap.add_argument("--name", default=None, help="nome do personagem (padrao: derivado da entrada)")
    ap.add_argument("--size", type=int, default=None, help="tamanho do sprite (ex.: 64 = 64x64)")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "default.json")
    ap.add_argument("--blender", default=None, help="caminho do blender.exe (se nao usar o modulo bpy)")
    ap.add_argument("--resolution", type=int, default=512, help="resolucao do render antes de pixelizar")
    ap.add_argument("--engine", default=None, help="motor Blender (EEVEE/CYCLES/WORKBENCH); auto se vazio")
    ap.add_argument("--elevation", type=float, default=None, help="angulo da camera (45-60 = estilo RO); usa o config se vazio")
    ap.add_argument("--image-res", default=None, help='caminho da imagem no Godot (ex.: "res://sprites/hero.png")')
    args = ap.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    kind = classify(args.entrada)
    if kind == "arquivo_desconhecido":
        print(f"[criar] ERRO: arquivo nao suportado: {args.entrada}", file=sys.stderr)
        sys.exit(2)

    # nome do personagem
    if args.name:
        name = args.name
    elif kind == "text":
        name = _slug(args.entrada)
    else:
        name = Path(args.entrada).stem

    # aplica o tamanho pedido (ex.: 64x64)
    if args.size:
        config.setdefault("sheet", {})["cell_w"] = args.size
        config["sheet"]["cell_h"] = args.size
        config.setdefault("pixelize", {})["target_height"] = args.size

    work = ROOT / "work" / name
    out_base = ROOT / "output" / name
    print(f"[criar] entrada detectada: {kind.upper()}  | personagem: {name}")

    image_path: Path | None = None
    model_path: Path | None = None

    # Fase 1: texto -> imagem
    if kind == "text":
        image_path = work / "concept.png"
        run_concept(args.entrada, image_path, args.size or 64)
        kind = "image"

    # Fases 2-3: imagem -> 3D -> rig+animacoes
    if kind == "image":
        if image_path is None:
            image_path = Path(args.entrada)
        glb = work / "modelo.glb"
        run_gerar3d(image_path, glb)
        animated = work / "animado.glb"
        run_rig(glb, animated, args.config)
        model_path = animated
        kind = "model"

    # Fase 4: render das direcoes
    if kind == "model":
        if model_path is None:
            model_path = Path(args.entrada)
        render_source = work / "render"
        run_render(model_path, render_source, args.config, args.resolution, args.engine, args.blender, args.elevation)
    elif kind == "frames":
        render_source = Path(args.entrada)
        print(f"[criar] usando frames existentes de {render_source}")
    else:
        print(f"[criar] ERRO: estado inesperado ({kind})", file=sys.stderr)
        sys.exit(2)

    # Fase 5: pixeliza -> espelha -> folha -> Godot
    frames_dir = work / "frames"
    prepare_frames(render_source, frames_dir, config)
    mirror_directions(frames_dir, config)

    out_base.parent.mkdir(parents=True, exist_ok=True)
    packer.pack(frames_dir, out_base, config)

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
