#!/usr/bin/env python3
"""FASE 3 -- rig (esqueleto) + animacoes. O elo mais dificil do pipeline.

Objetivo: pegar o modelo 3D (do gerar3d.py), gerar um esqueleto automatico e
aplicar as animacoes (idle/walk/attack/sit/hurt/dead), exportando um .glb ANIMADO
que a Fase 4 (render) usa.

ESTADO (honesto): este e um SCAFFOLD. Duas partes:
  (A) auto-rig com UniRig  -> chamada externa, config-driven; confirme o comando
      no README do UniRig (https://github.com/VAST-AI-Research/UniRig) ao instalar.
  (B) aplicar/retargetar animacoes CC0 (Quaternius/Truebones) no esqueleto -> este
      e o sub-problema em aberto (retargeting entre esqueletos). Ainda NAO resolvido.

Nada aqui foi testado numa GPU. Rode em casa e me traga os erros para ajustarmos.

    venv3d\\Scripts\\python src/rig.py --input work/hero/modelo.glb --out work/hero/animado.glb
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIRIG_DIR = ROOT / "third_party" / "UniRig"


def auto_rig_unirig(model_in: Path, rigged_out: Path) -> bool:
    """(A) Gera esqueleto+skinning com o UniRig. Retorna True se produziu o arquivo.

    O UniRig e config-driven (usa launch/inference/*.sh + configs/). O comando abaixo
    e um PONTO DE INTEGRACAO: ajuste conforme o README ao instalar em casa. Da para
    sobrescrever tudo pela variavel de ambiente UNIRIG_CMD (use {in} e {out}).
    """
    run_py = UNIRIG_DIR / "run.py"
    if not run_py.is_file():
        print(f"[rig] UniRig nao encontrado em {UNIRIG_DIR}.\n"
              "      Clone: git clone https://github.com/VAST-AI-Research/UniRig third_party/UniRig\n"
              "      e siga o README (baixa os pesos no HuggingFace, sem login).", file=sys.stderr)
        return False

    tmpl = os.environ.get("UNIRIG_CMD")
    if tmpl:
        cmd = tmpl.format(**{"in": str(model_in), "out": str(rigged_out)}).split()
    else:
        # PALPITE razoavel baseado no run.py do UniRig -- CONFIRME no README.
        cmd = [sys.executable, str(run_py), "--input", str(model_in), "--output", str(rigged_out)]

    print(f"[rig] (A) auto-rig UniRig: {' '.join(cmd)}")
    print("[rig]     (se falhar, ajuste o comando via env UNIRIG_CMD ou edite auto_rig_unirig)")
    subprocess.run(cmd, check=True, cwd=str(UNIRIG_DIR))
    return rigged_out.is_file()


def apply_animations(rigged_glb: Path, animated_out: Path, config_path: Path) -> None:
    """(B) Aplica/retargeta as animacoes CC0 no esqueleto (via Blender/bpy).

    SUB-PROBLEMA EM ABERTO: retargeting entre o esqueleto do UniRig e o esqueleto
    das animacoes mocap (Quaternius/Truebones) exige mapear os ossos. Caminhos:
      - addon de retarget no Blender (ex.: Rokoko, Auto-Rig Pro remap), OU
      - biblioteca de animacoes ja no MESMO esqueleto que o auto-rig produz.
    Por enquanto, se nao houver retarget, exportamos ao menos o modelo RIGADO
    (parado), que ja permite renderizar as 8 direcoes do 'idle'.
    """
    print("[rig] (B) aplicar animacoes: retargeting ainda NAO implementado.")
    print("[rig]     Exportando o modelo rigado (idle) para nao travar o pipeline.")
    # bpy roda dentro do python (mesmo truque do render). Aqui so copiamos/normalizamos.
    try:
        import bpy  # noqa: F401
    except ImportError:
        # sem bpy neste ambiente: apenas copia o arquivo rigado
        import shutil
        shutil.copyfile(rigged_glb, animated_out)
        return
    # com bpy disponivel, reexporta limpo (placeholder p/ futura logica de retarget)
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(rigged_glb))
    bpy.ops.export_scene.gltf(filepath=str(animated_out), export_format="GLB")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fase 3: rig + animacoes (scaffold; testar na GPU).")
    ap.add_argument("--input", required=True, type=Path, help="modelo 3D (.glb) do gerar3d")
    ap.add_argument("--out", required=True, type=Path, help=".glb animado de saida")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "default.json")
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rigged = args.out.with_name(args.out.stem + "_rigged.glb")

    if not auto_rig_unirig(args.input, rigged):
        raise SystemExit("[rig] auto-rig falhou/ausente. Veja as instrucoes acima.")

    apply_animations(rigged, args.out, args.config)
    print(f"[rig] PRONTO (parcial): {args.out}\n"
          "[rig] LEMBRETE: animacoes reais dependem do retargeting (sub-problema em aberto).")


if __name__ == "__main__":
    main()
