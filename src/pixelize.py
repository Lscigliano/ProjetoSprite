#!/usr/bin/env python3
"""Pixeliza frames renderizados (3D) dando-lhes o aspecto de pixel art.

O que faz:
  - reduz a resolucao (o que gera o "degrau" caracteristico do pixel art);
  - opcionalmente quantiza a paleta para N cores;
  - preserva a transparencia binarizando o canal alpha (bordas nitidas).

Uso:
    # um arquivo:
    py src/pixelize.py --input frame.png --output out.png --height 64 --colors 32
    # uma arvore de pastas (work/<anim>/<dir>/*.png):
    py src/pixelize.py --input work/render --output work/px --height 64 --colors 32
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def pixelize_image(
    img: Image.Image,
    target_height: int,
    colors: int = 0,
    alpha_threshold: int = 128,
) -> Image.Image:
    """Retorna uma copia pixelizada de `img` (RGBA)."""
    img = img.convert("RGBA")
    w, h = img.size

    if target_height and h > target_height:
        scale = target_height / h
        new_w = max(1, round(w * scale))
        img = img.resize((new_w, target_height), Image.LANCZOS)

    r, g, b, a = img.split()
    # Bordas nitidas: alpha vira 0 ou 255.
    a = a.point(lambda v: 255 if v >= alpha_threshold else 0)

    if colors and colors > 0:
        rgb = Image.merge("RGB", (r, g, b))
        rgb = rgb.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE)
        rgb = rgb.convert("RGB")
        r, g, b = rgb.split()

    return Image.merge("RGBA", (r, g, b, a))


def _process_file(src: Path, dst: Path, height: int, colors: int, alpha_threshold: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        out = pixelize_image(im, height, colors, alpha_threshold)
    out.save(dst)


def process_path(
    input_path: Path,
    output_path: Path,
    height: int,
    colors: int,
    alpha_threshold: int,
) -> int:
    """Processa um arquivo ou uma arvore inteira. Retorna a contagem de imagens."""
    if input_path.is_file():
        _process_file(input_path, output_path, height, colors, alpha_threshold)
        return 1

    count = 0
    for src in sorted(input_path.rglob("*.png")):
        rel = src.relative_to(input_path)
        _process_file(src, output_path / rel, height, colors, alpha_threshold)
        count += 1
    return count


def main() -> None:
    ap = argparse.ArgumentParser(description="Pixeliza frames para o look de pixel art.")
    ap.add_argument("--input", required=True, type=Path, help="arquivo PNG ou pasta")
    ap.add_argument("--output", required=True, type=Path, help="arquivo ou pasta de saida")
    ap.add_argument("--height", type=int, default=64, help="altura alvo em pixels (0 = nao reduz)")
    ap.add_argument("--colors", type=int, default=32, help="cores da paleta (0 = mantem)")
    ap.add_argument("--alpha-threshold", type=int, default=128, help="limiar de recorte do alpha (0-255)")
    args = ap.parse_args()

    n = process_path(args.input, args.output, args.height, args.colors, args.alpha_threshold)
    print(f"[pixelize] {n} imagem(ns) processada(s) -> {args.output}")


if __name__ == "__main__":
    main()
