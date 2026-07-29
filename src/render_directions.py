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
    # blender --python script -- ARGS  => pega depois do "--"
    # py script.py ARGS               => usa os argumentos normais
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = argv[1:]
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="config/default.json")
    ap.add_argument("--resolution", type=int, default=512, help="resolucao do render antes de pixelizar")
    ap.add_argument("--engine", default=None,
                    help="motor de render: BLENDER_EEVEE_NEXT / CYCLES / BLENDER_WORKBENCH")
    ap.add_argument("--elevation", type=float, default=None,
                    help="angulo da camera em graus (30=isometrico, 45-60=top-down RO, 90=top-down reto)")
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
        _remove_gltf_joint_placeholders(bpy)
        if ext == ".glb":
            _recover_vertex_color_from_glb(bpy, path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise SystemExit(f"[render] formato nao suportado: {ext}")


def _read_glb_json(path: Path):
    """Le os chunks JSON e BIN de um .glb (formato binario glTF 2.0), sem
    depender do bpy -- so struct/json puros."""
    import struct
    import json as json_module

    data = path.read_bytes()
    offset = 12  # header: magic(4) + version(4) + length(4)
    json_chunk, bin_chunk = None, None
    while offset < len(data):
        chunk_len, chunk_type = struct.unpack("<II", data[offset:offset + 8])
        chunk_data = data[offset + 8:offset + 8 + chunk_len]
        if chunk_type == 0x4E4F534A:  # b'JSON'
            json_chunk = json_module.loads(chunk_data)
        elif chunk_type == 0x004E4942:  # b'BIN\0'
            bin_chunk = chunk_data
        offset += 8 + chunk_len
    return json_chunk, bin_chunk


def _recover_vertex_color_from_glb(bpy, path: Path):
    """Contorna um bug real do importador glTF do Blender 5.2: quando um mesh
    tem tanto COLOR_0 (vertex color) quanto JOINTS_0/WEIGHTS_0 (skinning), o
    Blender falha silenciosamente em recriar o Color Attribute + material ao
    reimportar (confirmado: os dados COLOR_0 EXISTEM corretamente no arquivo
    .glb, o bug e so na reconstrucao da cena Blender, nao no arquivo).

    Sintoma sem este fix: personagem sai cinza/sem cor em qualquer render
    (EEVEE, Cycles ou Workbench com color_type=VERTEX), mesmo com boa luz.

    Fix: le o accessor COLOR_0 direto do binario do .glb e recria o Color
    Attribute + material manualmente no mesh reimportado. So roda se o
    Blender realmente falhou (mesh sem color_attributes) -- se um dia o bug
    for corrigido upstream, esta funcao vira no-op."""
    import struct

    mesh_objs = [o for o in bpy.data.objects if o.type == "MESH"]
    if not mesh_objs:
        return
    mesh_obj = max(mesh_objs, key=lambda o: len(o.data.vertices))
    if len(mesh_obj.data.color_attributes) > 0:
        return  # importador funcionou normalmente, nada a fazer

    gltf, bin_data = _read_glb_json(path)
    if gltf is None or bin_data is None:
        return

    # acha a primitive do mesh com mais vertices (mesmo criterio do mesh_obj)
    target_prim = None
    for m in gltf.get("meshes", []):
        for prim in m.get("primitives", []):
            acc = gltf["accessors"][prim["attributes"]["POSITION"]]
            if acc["count"] == len(mesh_obj.data.vertices) and "COLOR_0" in prim["attributes"]:
                target_prim = prim
                break
        if target_prim:
            break
    if target_prim is None:
        return  # arquivo nao tem COLOR_0 pra esse mesh; nada a recuperar

    acc = gltf["accessors"][target_prim["attributes"]["COLOR_0"]]
    bv = gltf["bufferViews"][acc["bufferView"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    comp_size = {"VEC3": 3, "VEC4": 4}[acc["type"]]
    fmt = f"<{comp_size}f"  # componentType 5126 = FLOAT (unico usado pelo nosso export)
    stride = struct.calcsize(fmt)

    ca = mesh_obj.data.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="POINT")
    for i in range(acc["count"]):
        off = start + i * stride
        vals = struct.unpack(fmt, bin_data[off:off + stride])
        ca.data[i].color = (vals[0], vals[1], vals[2], vals[3] if comp_size == 4 else 1.0)

    mat = bpy.data.materials.new("RecoveredColorMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    vc_node = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    vc_node.layer_name = "Color"
    mat.node_tree.links.new(vc_node.outputs["Color"], bsdf.inputs["Base Color"])
    mesh_obj.data.materials.append(mat)
    print(f"[render] cor recuperada manualmente ({acc['count']} vertices) -- bug do importador glTF contornado")


def _remove_gltf_joint_placeholders(bpy):
    """O importador glTF do Blender cria um mesh 'Icosphere' generico (~2x2x2
    unidades) como widget visual quando o armature nao tem custom shapes
    definidos (nosso caso: rig manual sem widgets). E so cosmetico na UI, mas
    infla MUITO a bounding box (bug real ja causou personagem minusculo na
    celula do sprite -- o Icosphere e maior que o proprio mesh do personagem).
    Sem vertex groups/parent: nunca e o mesh real, seguro remover sempre."""
    for obj in list(bpy.data.objects):
        if obj.name == "Icosphere" and obj.type == "MESH" and len(obj.vertex_groups) == 0:
            bpy.data.objects.remove(obj, do_unlink=True)


def _scene_bounds(bpy):
    """Retorna (centro, altura, raio_horizontal) aproximados dos objetos de malha.
    raio_horizontal = maior extensao em X ou Y (usado para calcular o enquadramento
    real da camera top-down, onde o personagem gira em Z durante o render)."""
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
    horizontal_radius = max(maxs[0] - mins[0], maxs[1] - mins[1]) / 2.0
    return center, height, horizontal_radius


def _setup_camera(bpy, center, height, horizontal_radius, elevation_deg, ortho):
    from mathutils import Vector
    import math as m

    cam_data = bpy.data.cameras.new("SpriteCam")
    cam_data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        # Altura APARENTE na tela: numa camera top-down inclinada (elevation_deg), a
        # extensao vertical projetada e height*sin(elev) + 2*horizontal_radius*cos(elev)
        # (o personagem gira em Z durante o render, entao qualquer lado horizontal pode
        # ficar de frente pra camera -- usa o raio, nao so a profundidade parada).
        # Margem pequena (1.15) so pra nao cortar por arredondamento/pose extrema.
        elev = m.radians(elevation_deg)
        apparent_height = height * m.sin(elev) + 2 * horizontal_radius * m.cos(elev)
        cam_data.ortho_scale = apparent_height * 1.15 if apparent_height > 0 else 2.0
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


def _setup_lighting(bpy, center, height):
    """Luz solar fixa (mundo) + ambiente. Fica parada enquanto o modelo gira,
    dando sombreamento consistente entre as 8 direcoes (padrao isometrico).

    O TripoSR gera cor via Vertex Color (nao textura de imagem) ligado ao
    Base Color do material -- fica visivel no Workbench (usa "Studio Light"
    sempre ligado), mas em EEVEE/Cycles precisa de luz de verdade incidindo
    pra nao sair escuro/sem graca. Energia calibrada visualmente (0.6 de
    ambiente deixava a cor quase invisivel em EEVEE)."""
    sun_data = bpy.data.lights.new("SpriteSun", type="SUN")
    sun_data.energy = 4.0
    sun = bpy.data.objects.new("SpriteSun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.location = (center[0], center[1], center[2] + max(height, 1.0) * 3)
    sun.rotation_euler = (math.radians(45), 0.0, math.radians(30))

    # 2a luz de preenchimento do lado oposto, pra nao deixar metade do
    # personagem escura demais enquanto ele gira nas 8 direcoes.
    fill_data = bpy.data.lights.new("SpriteFill", type="SUN")
    fill_data.energy = 2.0
    fill = bpy.data.objects.new("SpriteFill", fill_data)
    bpy.context.scene.collection.objects.link(fill)
    fill.location = (center[0], center[1], center[2] + max(height, 1.0) * 3)
    fill.rotation_euler = (math.radians(45), 0.0, math.radians(30 + 180))

    world = bpy.context.scene.world or bpy.data.worlds.new("SpriteWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[1].default_value = 1.2  # forca da luz ambiente


def _setup_render(bpy, resolution, engine=None):
    scene = bpy.context.scene

    # ordem de tentativa: o pedido -> EEVEE (GPU) -> CYCLES (CPU, headless-safe) -> WORKBENCH
    candidates = [engine] if engine else []
    candidates += ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH"]
    chosen = None
    for eng in candidates:
        if not eng:
            continue
        try:
            scene.render.engine = eng
            chosen = scene.render.engine
            break
        except (TypeError, Exception):
            continue
    print(f"[render] motor: {chosen}")

    if chosen == "CYCLES":
        # CPU e o mais confiavel em headless sem GPU dedicada
        scene.cycles.device = "CPU"
        scene.cycles.samples = 16

    if chosen == "BLENDER_WORKBENCH":
        # mostra a TEXTURA do modelo (senao sai cinza) + luz de estudio
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "TEXTURE"

    # AgX (color management padrao do Blender 4+/5) dessatura MUITO as cores
    # de vertex color do TripoSR -- personagem saia cinza/lavado em EEVEE e
    # Cycles mesmo com boa iluminacao (bug real ja depurado). "Standard" e
    # o view transform classico (sem tonemapping), preserva a cor de verdade.
    scene.view_settings.view_transform = "Standard"

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
    # ABSOLUTO: o Blender resolve caminhos relativos de forma diferente (salvava em C:\work).
    out_root = Path(args.out).resolve()

    _clean_scene(bpy)
    _import_model(bpy, Path(args.model))

    center, height, horizontal_radius = _scene_bounds(bpy)
    elev = args.elevation if args.elevation is not None else config["camera"]["elevation_deg"]
    _setup_camera(bpy, center, height, horizontal_radius, elev, config["camera"]["orthographic"])
    _setup_lighting(bpy, center, height)
    engine = args.engine or config.get("render", {}).get("engine")
    _setup_render(bpy, args.resolution, engine)

    scene = bpy.context.scene
    roots = _root_objects(bpy)

    # pivot: rotacionamos os objetos raiz em torno do Z. Usamos um Empty como pai.
    pivot = bpy.data.objects.new("Pivot", None)
    scene.collection.objects.link(pivot)
    pivot.location = (center[0], center[1], 0.0)
    bpy.context.view_layer.update()  # garante matrix_world atualizada
    for r in roots:
        if r is pivot:
            continue
        r.parent = pivot
        # mantem o objeto no lugar (senao "teleporta" pelo offset do pivo)
        r.matrix_parent_inverse = pivot.matrix_world.inverted()

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
