#!/usr/bin/env python3
"""Monta um spritesheet a partir de uma arvore de frames + gera metadados JSON.

Estrutura de entrada esperada:
    <frames_dir>/<animacao>/<direcao>/0000.png, 0001.png, ...

Saida:
    <out>.png   -> a folha (grade), fundo transparente
    <out>.json  -> metadados (celula, animacoes, direcoes, retangulos, fps, loop)

Layout: uma LINHA por par (animacao, direcao); colunas = frames.
Cada frame e centralizado numa celula de tamanho fixo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def discover_frames(frames_dir: Path, animations, directions):
    """Retorna lista ordenada de (anim, dir, [Path,...]) apenas para pares existentes."""
    rows = []
    for anim in animations:
        for direction in directions:
            d = frames_dir / anim / direction
            if not d.is_dir():
                continue
            frames = sorted(d.glob("*.png"))
            if frames:
                rows.append((anim, direction, frames))
    return rows


def _fit_into_cell(frame: Image.Image, cell_w: int, cell_h: int) -> Image.Image:
    """Centraliza o frame numa celula transparente cell_w x cell_h (recorta se maior)."""
    frame = frame.convert("RGBA")
    cell = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    fw, fh = frame.size
    # ancora embaixo-centro (padrao para personagens: "pes" no mesmo nivel)
    x = (cell_w - fw) // 2
    y = cell_h - fh
    cell.alpha_composite(frame, (max(0, x), max(0, y)))
    return cell


def pack(frames_dir: Path, out_base: Path, config: dict) -> dict:
    anims_cfg = {a["name"]: a for a in config["animations"]}
    anim_order = [a["name"] for a in config["animations"]]
    dir_order = [d["name"] for d in config["directions"]]
    cell_w = config["sheet"]["cell_w"]
    cell_h = config["sheet"]["cell_h"]

    rows = discover_frames(frames_dir, anim_order, dir_order)
    if not rows:
        raise SystemExit(f"[pack] nenhum frame encontrado em {frames_dir}")

    max_cols = max(len(frames) for _, _, frames in rows)
    sheet_w = max_cols * cell_w
    sheet_h = len(rows) * cell_h
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    meta = {
        "image": out_base.with_suffix(".png").name,
        "cell": {"w": cell_w, "h": cell_h},
        "animations": {},
    }

    for row_idx, (anim, direction, frames) in enumerate(rows):
        rects = []
        for col_idx, fpath in enumerate(frames):
            with Image.open(fpath) as im:
                cell_img = _fit_into_cell(im, cell_w, cell_h)
            x = col_idx * cell_w
            y = row_idx * cell_h
            sheet.alpha_composite(cell_img, (x, y))
            rects.append([x, y, cell_w, cell_h])

        acfg = anims_cfg.get(anim, {})
        meta["animations"].setdefault(anim, {})[direction] = {
            "row": row_idx,
            "frames": len(frames),
            "fps": acfg.get("fps", 8),
            "loop": bool(acfg.get("loop", True)),
            "rects": rects,
        }

    out_base.parent.mkdir(parents=True, exist_ok=True)
    png_path = out_base.with_suffix(".png")
    json_path = out_base.with_suffix(".json")
    sheet.save(png_path)
    json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    total_frames = sum(len(f) for _, _, f in rows)
    print(f"[pack] {len(rows)} linhas, {total_frames} frames -> {png_path.name} ({sheet_w}x{sheet_h}) + {json_path.name}")
    return meta


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Monta spritesheet + JSON a partir de frames.")
    ap.add_argument("--frames", required=True, type=Path, help="pasta raiz dos frames (<anim>/<dir>/*.png)")
    ap.add_argument("--out", required=True, type=Path, help="caminho base de saida (sem extensao)")
    ap.add_argument("--config", type=Path, default=Path("config/default.json"))
    args = ap.parse_args()
    pack(args.frames, args.out, load_config(args.config))


if __name__ == "__main__":
    main()
