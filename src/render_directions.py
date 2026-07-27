#!/usr/bin/env python3
"""Renderiza um modelo 3D animado em 8 direcoes isometricas (script para o BLENDER).

NAO roda com o Python normal -- roda dentro do Blender (headless):

    blender --background --python src/render_directions.py -- \
        --model input/hero.glb --out work/render --config config/default.json

Para cada animacao (Action) do modelo e para cada direcao configurada, gira o
modelo no eixo Z e renderiza os frames com fundo transparente. Direcoes marcadas
como "mirror_of" NAO sao renderizadas aqui (o pipeline as gera por espelhamento).

Saida: work/render/<anim>/<dir>/0000.png ...
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def _parse_args(argv):
    # pega tudo depois do "--"
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="config/default.json")
    ap.add_argument("--resolution", type=int, default=512, help="resolucao do render antes de pixelizar")
    return ap.parse_args(argv)


def _clean_scene(bpy):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures):
        for item in list(block):
            block.remove(item)


def _import_model(bpy, path: Path):
    ext = path.suffix.lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise SystemExit(f"[render] formato nao suportado: {ext}")


def _scene_bounds(bpy):
    """Retorna (centro, altura) aproximados dos objetos de malha."""
    from mathutils import Vector
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            for i in range(3):
                mins[i] = min(mins[i], world[i])
                maxs[i] = max(maxs[i], world[i])
    center = (mins + maxs) / 2.0
    height = maxs[2] - mins[2]
    return center, height


def _setup_camera(bpy, center, height, elevation_deg, ortho):
    from mathutils import Vector
    import math as m

    cam_data = bpy.data.cameras.new("SpriteCam")
    cam_data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam_data.ortho_scale = height * 1.4 if height > 0 else 2.0
    cam = bpy.data.objects.new("SpriteCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)

    elev = m.radians(elevation_deg)
    dist = max(height, 1.0) * 3.0
    # camera no plano +Y, elevada; o MODELO e que gira em Z para dar as direcoes
    cam.location = Vector((
        center[0],
        center[1] - dist * m.cos(elev),
        center[2] + dist * m.sin(elev),
    ))
    # aponta para o centro
    direction = Vector(center) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def _setup_render(bpy, resolution):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if hasattr(scene.render, "engine") else "BLENDER_EEVEE"
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        try:
            scene.render.engine = "BLENDER_EEVEE"
        except Exception:
            pass
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.film_transparent = True  # fundo transparente
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"


def _root_objects(bpy):
    """Objetos de nivel superior (para rotacionar tudo junto)."""
    return [o for o in bpy.data.objects if o.parent is None and o.type in ("MESH", "ARMATURE", "EMPTY")]


def _iter_actions(bpy, anim_names):
    """Retorna dict nome_config -> Action, casando por nome (case-insensitive, substring)."""
    actions = {a.name: a for a in bpy.data.actions}
    matched = {}
    for cfg_name in anim_names:
        found = None
        for a_name, action in actions.items():
            if cfg_name.lower() in a_name.lower():
                found = action
                break
        matched[cfg_name] = found
    return matched


def main():
    import bpy  # disponivel apenas dentro do Blender
    from mathutils import Euler

    args = _parse_args(sys.argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out_root = Path(args.out)

    _clean_scene(bpy)
    _import_model(bpy, Path(args.model))

    center, height = _scene_bounds(bpy)
    _setup_camera(bpy, center, height, config["camera"]["elevation_deg"], config["camera"]["orthographic"])
    _setup_render(bpy, args.resolution)

    scene = bpy.context.scene
    roots = _root_objects(bpy)

    # pivot: rotacionamos os objetos raiz em torno do Z. Usamos um Empty como pai.
    pivot = bpy.data.objects.new("Pivot", None)
    scene.collection.objects.link(pivot)
    pivot.location = (center[0], center[1], 0.0)
    for r in roots:
        if r is pivot:
            continue
        r.parent = pivot

    anim_names = [a["name"] for a in config["animations"]]
    actions = _iter_actions(bpy, anim_names)

    # armature para aplicar as actions
    armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)

    render_dirs = [d for d in config["directions"] if not d.get("mirror_of")]
    offset = config["camera"].get("azimuth_offset_deg", 0.0)

    total = 0
    for anim in config["animations"]:
        action = actions.get(anim["name"])
        if action is None:
            print(f"[render] AVISO: animacao '{anim['name']}' nao encontrada no modelo; pulando.")
            continue
        if armature is not None:
            if armature.animation_data is None:
                armature.animation_data_create()
            armature.animation_data.action = action

        f_start = int(action.frame_range[0])
        f_end = int(action.frame_range[1])

        for d in render_dirs:
            az = math.radians(d["azimuth_deg"] + offset)
            pivot.rotation_euler = Euler((0.0, 0.0, az), "XYZ")
            out_dir = out_root / anim["name"] / d["name"]
            out_dir.mkdir(parents=True, exist_ok=True)

            idx = 0
            for f in range(f_start, f_end + 1):
                scene.frame_set(f)
                scene.render.filepath = str(out_dir / f"{idx:04d}.png")
                bpy.ops.render.render(write_still=True)
                idx += 1
                total += 1
            print(f"[render] {anim['name']}/{d['name']}: {idx} frames")

    print(f"[render] concluido: {total} frames em {out_root}")


if __name__ == "__main__":
    main()
