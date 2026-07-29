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


def _body_geometry(mesh_obj):
    """Medidas do corpo derivadas do bounding-box, usadas tanto pro esqueleto
    (_build_simple_humanoid) quanto pra posicionar acessorios (_add_bow_geometry)
    com a MESMA referencia -- evita formulas duplicadas divergindo com o tempo."""
    min_co, max_co = _mesh_bounds(mesh_obj)
    height = max_co.z - min_co.z
    z0 = min_co.z
    cx, cy = (min_co.x + max_co.x) / 2, (min_co.y + max_co.y) / 2
    half_width = (max_co.x - min_co.x) / 2
    return cx, cy, z0, height, half_width


def _build_simple_humanoid(bpy, mesh_obj):
    """Cria um armature humanoide de 19 ossos, escalado/posicionado pelo
    bounding-box do mesh. Posicoes em fracao da altura (0=pes, 1=topo da
    cabeca) -- calibrado para a proporcao chibi que os requisitos de arte
    do projeto pedem (cabeca grande), ver DESIGN.md / HANDOFF.md.
    """
    cx, cy, z0, height, half_width = _body_geometry(mesh_obj)

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
    """ARMATURE_ENVELOPE (baseado em distancia/envelope) em vez de
    ARMATURE_AUTO (Bone Heat, baseado em difusao de calor pela malha):
    o Bone Heat falha silenciosamente e de forma intermitente nas malhas
    do TripoSR (warning "failed to find solution for one or more bones",
    produzindo deformacao quebrada ou ate export sem skin nenhum). Envelope
    e mais tolerante a geometria imperfeita e deu resultado consistente em
    todos os testes desta sessao."""
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_ENVELOPE")


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


def _apply_animations(bpy, rig, classe: str = "guerreiro"):
    """Kit padrao MMO 2D (ver config/default.json): idle, walk, attack, sit,
    hurt, dead. Poses-chave codificadas a mao (nao mocap) -- ver HANDOFF.md
    para o porque dessa escolha.

    A pose de "attack" muda por classe (guerreiro/mago/arqueiro) -- as
    outras 5 animacoes sao compartilhadas, ja que nao dependem de arma."""

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
    if classe == "arqueiro":
        # tiro de arco: braco esquerdo (L) sustenta o arco esticado pra
        # frente e parado (segura o arco, ver _add_bow_geometry), braco
        # direito (R) puxa a corda ate o ombro (frames 1-6) e solta (10).
        key("upper_arm.L", 1, (0, 0, -75))
        key("forearm.L", 1, (0, 0, 0))
        key("upper_arm.R", 1, (0, 0, 0))
        key("forearm.R", 1, (0, 0, 0))
        key("upper_arm.L", 6, (0, 0, -75))
        key("forearm.L", 6, (0, 0, 0))
        key("upper_arm.R", 6, (10, 0, -55))
        key("forearm.R", 6, (110, 0, 0))
        key("upper_arm.L", 10, (0, 0, -75))
        key("forearm.L", 10, (0, 0, 0))
        key("upper_arm.R", 10, (-10, 0, -20))
        key("forearm.R", 10, (20, 0, 0))
        key("upper_arm.L", 12, (0, 0, 0))
        key("forearm.L", 12, (0, 0, 0))
        key("upper_arm.R", 12, (0, 0, 0))
        key("forearm.R", 12, (0, 0, 0))
    elif classe == "mago":
        # conjuracao: os dois bracos sobem e se aproximam na frente do
        # peito (gesto de "canalizar"), com um pico de tensao no meio.
        key("upper_arm.L", 1, (0, 0, 0))
        key("upper_arm.R", 1, (0, 0, 0))
        key("forearm.L", 1, (0, 0, 0))
        key("forearm.R", 1, (0, 0, 0))
        key("upper_arm.L", 5, (-60, 0, -40))
        key("upper_arm.R", 5, (-60, 0, 40))
        key("forearm.L", 5, (60, 0, 0))
        key("forearm.R", 5, (60, 0, 0))
        key("chest", 5, (-6, 0, 0))
        key("upper_arm.L", 9, (-70, 0, -30))
        key("upper_arm.R", 9, (-70, 0, 30))
        key("forearm.L", 9, (70, 0, 0))
        key("forearm.R", 9, (70, 0, 0))
        key("chest", 9, (0, 0, 0))
        key("upper_arm.L", 12, (0, 0, 0))
        key("upper_arm.R", 12, (0, 0, 0))
        key("forearm.L", 12, (0, 0, 0))
        key("forearm.R", 12, (0, 0, 0))
    else:  # "guerreiro" (padrao): golpe generico de braco/arma corpo-a-corpo
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


def _add_bow_geometry(bpy, mesh_obj):
    """Cria um arco simples (curva bezier convertida em malha) posicionado
    na mao esquerda (mesma formula de posicao usada em _build_simple_humanoid
    pra hand.L) e FUNDE com o mesh do personagem, ANTES do skinning.

    Por que fundir em vez de parentear como objeto separado: o parenting
    osso-a-objeto (`parent_set(type="BONE")`) se mostrou bugado nesta sessao
    -- a matriz calculada nao correspondia a posicao real do osso mesmo com
    os dados de entrada corretos (nao foi possivel isolar a causa). Fundindo
    o arco ANTES do skin, ele ganha peso de vertice automaticamente pelo
    ARMATURE_ENVELOPE (mesmo mecanismo que ja deforma o resto do corpo
    corretamente) -- sem parenting manual, sem matrizes.
    """
    cx, cy, z0, height, half_width = _body_geometry(mesh_obj)
    z_hand = z0 + 0.55 * height  # mesma fracao de hand.L em _build_simple_humanoid
    hand_x = cx + half_width * 0.95 * 1.05  # um pouco alem da mao (punho fechado)

    curve_data = bpy.data.curves.new("BowCurve", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.bevel_depth = height * 0.008
    curve_data.resolution_u = 12
    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(2)  # total 3 pontos: base, meio (curvatura), topo

    bow_len = height * 0.35
    bow_bend = height * 0.06
    # arco na vertical (eixo Z mundial), "barriga" curvando no eixo Y
    pts = [
        (hand_x, cy, z_hand - bow_len / 2),
        (hand_x - bow_bend, cy, z_hand),
        (hand_x, cy, z_hand + bow_len / 2),
    ]
    for i, p in enumerate(pts):
        bp = spline.bezier_points[i]
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"

    bow_obj = bpy.data.objects.new("Bow", curve_data)
    bpy.context.collection.objects.link(bow_obj)

    # converte curva -> malha (join so funciona entre meshes, nao curva+mesh)
    bpy.context.view_layer.objects.active = bow_obj
    bpy.ops.object.select_all(action="DESELECT")
    bow_obj.select_set(True)
    bpy.ops.object.convert(target="MESH")

    mat = bpy.data.materials.new("BowMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.30, 0.18, 0.08, 1.0)  # marrom madeira
    bow_obj.data.materials.append(mat)

    # funde no mesh do personagem (join real: geometria unificada num so
    # objeto/mesh, herda skin automaticamente depois)
    bpy.ops.object.select_all(action="DESELECT")
    bow_obj.select_set(True)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.join()
    return mesh_obj


def build_rig(bpy, model_in: Path, out_glb: Path, classe: str = "guerreiro") -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model_in))

    mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")
    _normalize_triposr_orientation(bpy, mesh_obj)

    # o arco precisa ser fundido ANTES do rig+skin: a geometria calcula sua
    # posicao pelo bounding-box do mesh (mesma referencia do esqueleto), e
    # so entao o ARMATURE_ENVELOPE (chamado por _skin) da peso de vertice
    # pro arco automaticamente, junto com o resto do corpo.
    if classe == "arqueiro":
        mesh_obj = _add_bow_geometry(bpy, mesh_obj)

    rig = _build_simple_humanoid(bpy, mesh_obj)
    _skin(bpy, mesh_obj, rig)
    _apply_animations(bpy, rig, classe=classe)

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
    ap.add_argument("--classe", default="guerreiro", choices=["guerreiro", "mago", "arqueiro"],
                     help="muda a pose de 'attack' e acessorios (arqueiro ganha um arco na mao)")
    args = ap.parse_args()

    try:
        import bpy  # noqa: F401
    except ImportError:
        raise SystemExit(
            "[rig] este script precisa rodar dentro do bpy (venv_bpy, Python 3.13).\n"
            "      venv_bpy\\Scripts\\python src\\rig.py --input ... --out ..."
        )
    import bpy

    build_rig(bpy, args.input, args.out, classe=args.classe)
    print(f"[rig] PRONTO: {args.out}")
    print("[rig] animacoes: idle, walk, attack, sit, hurt, dead (poses codificadas, nao mocap)")


if __name__ == "__main__":
    main()
