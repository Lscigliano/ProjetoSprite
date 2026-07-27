#!/usr/bin/env python3
"""Gera um recurso SpriteFrames (.tres) do Godot 4 a partir do spritesheet + JSON.

Cada par (animacao, direcao) vira uma animacao chamada "<anim>_<dir>"
(ex.: walk_S, attack_NE). Cada frame vira uma AtlasTexture apontando para
a mesma imagem da folha, com a regiao (Rect2) correta.

Uso:
    py src/godot_export.py --meta output/hero.json --image-res "res://sprites/hero.png" --out output/hero_frames.tres
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_tres(meta: dict, image_res_path: str) -> str:
    """Monta o texto do .tres (Godot 4, format=3)."""
    ext_id = "1_sheet"

    atlas_blocks = []
    anim_entries = []
    sub_counter = 0

    for anim_name, dirs in meta["animations"].items():
        for dir_name, info in dirs.items():
            frame_refs = []
            for rect in info["rects"]:
                sub_id = f"AtlasTexture_{sub_counter:05d}"
                sub_counter += 1
                x, y, w, h = rect
                atlas_blocks.append(
                    f'[sub_resource type="AtlasTexture" id="{sub_id}"]\n'
                    f'atlas = ExtResource("{ext_id}")\n'
                    f'region = Rect2({x}, {y}, {w}, {h})\n'
                )
                frame_refs.append(
                    f'{{\n"duration": 1.0,\n"texture": SubResource("{sub_id}")\n}}'
                )

            frames_joined = ", ".join(frame_refs)
            anim_entries.append(
                "{\n"
                f'"frames": [{frames_joined}],\n'
                f'"loop": {"true" if info["loop"] else "false"},\n'
                f'"name": &"{anim_name}_{dir_name}",\n'
                f'"speed": {float(info["fps"])}\n'
                "}"
            )

    # load_steps = 1 (ext) + N sub-resources + 1 (o proprio resource)
    load_steps = 1 + sub_counter + 1

    header = f'[gd_resource type="SpriteFrames" load_steps={load_steps} format=3]\n'
    ext = f'\n[ext_resource type="Texture2D" path="{image_res_path}" id="{ext_id}"]\n'
    subs = "\n" + "\n".join(atlas_blocks)
    anims_joined = ", ".join(anim_entries)
    resource = f'\n[resource]\nanimations = [{anims_joined}]\n'

    return header + ext + subs + resource


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera SpriteFrames .tres para Godot 4.")
    ap.add_argument("--meta", required=True, type=Path, help="JSON gerado pelo pack_spritesheet")
    ap.add_argument("--out", required=True, type=Path, help="caminho do .tres de saida")
    ap.add_argument(
        "--image-res",
        default=None,
        help='caminho da imagem no Godot (ex.: "res://sprites/hero.png"). '
        'Padrao: res://<nome-da-imagem-no-json>',
    )
    args = ap.parse_args()

    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    image_res = args.image_res or f'res://{meta["image"]}'

    tres = build_tres(meta, image_res)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(tres, encoding="utf-8")

    n_anims = sum(len(d) for d in meta["animations"].values())
    print(f"[godot] {n_anims} animacoes ('<anim>_<dir>') -> {args.out.name} (imagem: {image_res})")


if __name__ == "__main__":
    main()
