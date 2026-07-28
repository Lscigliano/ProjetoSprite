#!/usr/bin/env python3
"""FASE 3 -- rig (esqueleto) + skin + animacoes.

Roda dentro do modulo bpy (venv_bpy, Python 3.13 -- NAO no venv3d, que so tem
torch/TripoSR e nao tem bpy). Pega o .glb estatico da Fase 2 (TripoSR) e produz
um .glb ANIMADO (idle/walk/attack/sit/hurt/dead) que a Fase 4 (render) usa.

Historico (o que NAO funcionou, documentado para nao repetir):
  - UniRig: assume Linux + compilacao CUDA (spconv) fragil, sem build p/ CUDA
    12.8/13; nem faz retargeting de animacao mesmo se rodasse. Abandonado.
  - Rigify (addon nativo do Blender): auto-rig funciona headless, mas as
    constraints "Copy Transforms" que propagam a pose dos controles (FK/IK)
    ate os ossos DEF- dependem de DRIVERS que nao recalculam em modo
    `--background` (confirmado com 6+ tentativas de forcar via depsgraph/
    frame_set/view_layer.update -- nenhuma funcionou). Abandonado.

Solucao adotada: esqueleto humanoide SIMPLES (~19 ossos, sem camadas de
controle IK/FK/tweak), construido e escalado por bounding-box a cada mesh,
com animacoes codificadas via keyframes diretos nos ossos de deformacao.
Validado headless: deformacao real confirmada (poses extremas testadas).

    venv_bpy\\Scripts\\python src/rig.py --input work/hero/modelo.glb --out work/hero/animado.glb
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _normalize_triposr_orientation(bpy, mesh_obj):
    """TripoSR exporta o mesh deitado (nao Z-up). Convencao fixa, confirmada
    em 2 modelos (personagem chibi + raposa): rotacionar -90 em X, depois 90
    em Z, coloca o personagem em pe e de frente pra camera (-Y).

    IMPORTANTE: o objeto pai do glTF importado usa rotation_mode=QUATERNION;
    setar rotation_euler nele e um no-op silencioso (bug real ja encontrado).
    """
    import mathutils as mu

    world_empty = mesh_obj.parent
    if world_empty is None:
        return
    q1 = mu.Quaternion((1, 0, 0), math.radians(-90))
    q2 = mu.Quaternion((0, 0, 1), math.radians(90))
    world_empty.rotation_quaternion = q2 @ q1
    bpy.context.view_layer.update()

    mesh_obj.matrix_world = world_empty.matrix_world @ mesh_obj.matrix_world
    mesh_obj.parent = None
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.data.objects.remove(world_empty, do_unlink=True)


def _mesh_bounds(mesh_obj):
    import mathutils as mu

    min_co = mu.Vector((1e9, 1e9, 1e9))
    max_co = mu.Vector((-1e9, -1e9, -1e9))
    for corner in mesh_obj.bound_box:
        wc = mesh_obj.matrix_world @ mu.Vector(corner)
        min_co.x, min_co.y, min_co.z = min(min_co.x, wc.x), min(min_co.y, wc.y), min(min_co.z, wc.z)
        max_co.x, max_co.y, max_co.z = max(max_co.x, wc.x), max(max_co.y, wc.y), max(max_co.z, wc.z)
    return min_co, max_co


def _build_simple_humanoid(bpy, mesh_obj):
    """Cria um armature humanoide de 19 ossos, escalado/posicionado pelo
    bounding-box do mesh. Posicoes em fracao da altura (0=pes, 1=topo da
    cabeca) -- calibrado para a proporcao chibi que os requisitos de arte
    do projeto pedem (cabeca grande), ver DESIGN.md / HANDOFF.md.
    """
    min_co, max_co = _mesh_bounds(mesh_obj)
    height = max_co.z - min_co.z
    z0 = min_co.z
    cx, cy = (min_co.x + max_co.x) / 2, (min_co.y + max_co.y) / 2
    half_width = (max_co.x - min_co.x) / 2

    def z(frac: float) -> float:
        return z0 + frac * height

    arm_data = bpy.data.armatures.new("rig")
    rig = bpy.data.objects.new("rig", arm_data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    def mkbone(name, head, tail, parent=None, connect=False):
        b = eb.new(name)
        b.head = head
        b.tail = tail
        if parent:
            b.parent = parent
            b.use_connect = connect
        return b

    pelvis = mkbone("pelvis", (cx, cy, z(0.42)), (cx, cy, z(0.48)))
    spine = mkbone("spine", (cx, cy, z(0.48)), (cx, cy, z(0.58)), pelvis, True)
    chest = mkbone("chest", (cx, cy, z(0.58)), (cx, cy, z(0.66)), spine, True)
    neck = mkbone("neck", (cx, cy, z(0.66)), (cx, cy, z(0.70)), chest, True)
    mkbone("head", (cx, cy, z(0.70)), (cx, cy, z(1.00)), neck, True)

    for side, sign in (("L", 1), ("R", -1)):
        shoulder_x = sign * half_width * 0.35
        hand_x = sign * half_width * 0.95
        shoulder = mkbone(f"shoulder.{side}", (cx, cy, z(0.64)), (cx + shoulder_x, cy, z(0.62)), chest)
        upper_arm = mkbone(f"upper_arm.{side}", (cx + shoulder_x, cy, z(0.62)), (cx + hand_x * 0.55, cy, z(0.58)), shoulder, True)
        forearm = mkbone(f"forearm.{side}", (cx + hand_x * 0.55, cy, z(0.58)), (cx + hand_x, cy, z(0.55)), upper_arm, True)
        mkbone(f"hand.{side}", (cx + hand_x, cy, z(0.55)), (cx + hand_x * 1.1, cy, z(0.53)), forearm, True)

    for side, sign in (("L", 1), ("R", -1)):
        hip_x = sign * half_width * 0.25
        thigh = mkbone(f"thigh.{side}", (cx + hip_x, cy, z(0.42)), (cx + hip_x, cy, z(0.22)), pelvis)
        shin = mkbone(f"shin.{side}", (cx + hip_x, cy, z(0.22)), (cx + hip_x, cy, z(0.03)), thigh, True)
        mkbone(f"foot.{side}", (cx + hip_x, cy, z(0.03)), (cx + hip_x, cy + height * 0.08, z(0.0)), shin, True)

    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def _skin(bpy, mesh_obj, rig):
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")


def _new_action(bpy, rig, name: str):
    action = bpy.data.actions.new(name=name)
    action.use_fake_user = True  # senao e apagada como orphan data ao trocar de action
    if rig.animation_data is None:
        rig.animation_data_create()
    rig.animation_data.action = action
    return action


def _reset_pose(bpy):
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.rot_clear()
    bpy.ops.pose.loc_clear()


def _apply_animations(bpy, rig):
    """Kit padrao MMO 2D (ver config/default.json): idle, walk, attack, sit,
    hurt, dead. Poses-chave codificadas a mao (nao mocap) -- ver HANDOFF.md
    para o porque dessa escolha."""

    def key(pb_name, frame, euler_deg):
        pb = rig.pose.bones[pb_name]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = tuple(math.radians(d) for d in euler_deg)
        pb.keyframe_insert(data_path="rotation_euler", frame=frame)

    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")

    _reset_pose(bpy)
    _new_action(bpy, rig, "idle")
    key("chest", 1, (2, 0, 0))
    key("chest", 8, (-2, 0, 0))
    key("chest", 16, (2, 0, 0))

    _reset_pose(bpy)
    _new_action(bpy, rig, "walk")
    frames = [1, 5, 9, 13, 17]
    leg_swing = [30, 0, -30, 0, 30]
    arm_swing = [-20, 0, 20, 0, -20]
    for i, f in enumerate(frames):
        key("thigh.L", f, (leg_swing[i], 0, 0))
        key("thigh.R", f, (-leg_swing[i], 0, 0))
        key("shin.L", f, (max(0, leg_swing[i] * 0.6), 0, 0))
        key("shin.R", f, (max(0, -leg_swing[i] * 0.6), 0, 0))
        key("upper_arm.L", f, (arm_swing[i], 0, 0))
        key("upper_arm.R", f, (-arm_swing[i], 0, 0))

    _reset_pose(bpy)
    _new_action(bpy, rig, "attack")
    key("upper_arm.R", 1, (0, 0, 0))
    key("forearm.R", 1, (0, 0, 0))
    key("upper_arm.R", 4, (60, 0, -20))
    key("forearm.R", 4, (40, 0, 0))
    key("upper_arm.R", 8, (-70, 0, 30))
    key("forearm.R", 8, (-20, 0, 0))
    key("upper_arm.R", 12, (0, 0, 0))
    key("forearm.R", 12, (0, 0, 0))

    _reset_pose(bpy)
    _new_action(bpy, rig, "sit")
    key("thigh.L", 1, (0, 0, 0))
    key("thigh.R", 1, (0, 0, 0))
    key("chest", 1, (0, 0, 0))
    key("thigh.L", 6, (85, 0, 0))
    key("thigh.R", 6, (85, 0, 0))
    key("shin.L", 6, (95, 0, 0))
    key("shin.R", 6, (95, 0, 0))
    key("chest", 6, (10, 0, 0))

    _reset_pose(bpy)
    _new_action(bpy, rig, "hurt")
    key("chest", 1, (0, 0, 0))
    key("pelvis", 1, (0, 0, 0))
    key("upper_arm.L", 1, (0, 0, 0))
    key("upper_arm.R", 1, (0, 0, 0))
    key("chest", 3, (-25, 0, 0))
    key("pelvis", 3, (10, 0, 0))
    key("upper_arm.L", 3, (30, 0, -20))
    key("upper_arm.R", 3, (30, 0, 20))
    key("chest", 8, (0, 0, 0))
    key("pelvis", 8, (0, 0, 0))
    key("upper_arm.L", 8, (0, 0, 0))
    key("upper_arm.R", 8, (0, 0, 0))

    _reset_pose(bpy)
    _new_action(bpy, rig, "dead")
    key("pelvis", 1, (0, 0, 0))
    key("chest", 1, (0, 0, 0))
    key("thigh.L", 1, (0, 0, 0))
    key("thigh.R", 1, (0, 0, 0))
    key("pelvis", 10, (-45, 0, 0))
    key("chest", 10, (-15, 0, 0))
    key("thigh.L", 10, (-20, 0, 0))
    key("thigh.R", 10, (-20, 0, 0))

    bpy.ops.object.mode_set(mode="OBJECT")


def build_rig(bpy, model_in: Path, out_glb: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model_in))

    mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")
    _normalize_triposr_orientation(bpy, mesh_obj)

    rig = _build_simple_humanoid(bpy, mesh_obj)
    _skin(bpy, mesh_obj, rig)
    _apply_animations(bpy, rig)

    out_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(out_glb),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_force_sampling=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Fase 3: rig + skin + animacoes (bpy).")
    ap.add_argument("--input", required=True, type=Path, help="modelo 3D (.glb) do gerar3d")
    ap.add_argument("--out", required=True, type=Path, help=".glb animado de saida")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "default.json")
    args = ap.parse_args()

    try:
        import bpy  # noqa: F401
    except ImportError:
        raise SystemExit(
            "[rig] este script precisa rodar dentro do bpy (venv_bpy, Python 3.13).\n"
            "      venv_bpy\\Scripts\\python src\\rig.py --input ... --out ..."
        )
    import bpy

    build_rig(bpy, args.input, args.out)
    print(f"[rig] PRONTO: {args.out}")
    print("[rig] animacoes: idle, walk, attack, sit, hurt, dead (poses codificadas, nao mocap)")


if __name__ == "__main__":
    main()
