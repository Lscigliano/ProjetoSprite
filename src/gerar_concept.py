#!/usr/bin/env python3
"""FASE 1 -- texto -> imagem de concept (Stable Diffusion LOCAL, na GPU).

Gera a "planta baixa" do personagem a partir de uma descricao em texto, ja no
estilo/pose que o pipeline 3D precisa (frente, pose A, maos vazias, sem
acessorios soltos, fundo branco). O look de pixel art final sai na Fase 5;
aqui geramos um concept limpo para a reconstrucao 3D funcionar bem.

ATENCAO (honesto): roda com GPU (venv3d) e um checkpoint local do Stable Diffusion.
NAO foi testado nesta maquina (sem GPU). Baixe um checkpoint open-source SEM login
(coloque em models/ ou passe --model com um caminho/ID) e ajuste se necessario.

    venv3d\\Scripts\\python src/gerar_concept.py --prompt "urso guerreiro chibi, armadura laranja" --out work/urso/concept.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

# Sufixo que forca o concept a nascer "amigavel ao 3D" (ver HANDOFF.md).
STYLE_SUFFIX = (
    "full body character concept, front view, A-pose, arms slightly away from body, "
    "empty open hands, symmetrical, no weapons, no loose accessories, no cape, "
    "plain solid white background, even flat lighting, no cast shadows, "
    "clean bold outlines, chibi proportions, game character model sheet"
)
NEGATIVE = (
    "weapon, bow, sword, bag, pouch, strap, cape, cloth, held items, action pose, "
    "dynamic pose, cropped, cut off, multiple characters, text, watermark, "
    "busy background, cast shadows, extra limbs, blurry"
)


def gerar(prompt: str, out: Path, model: str, steps: int, seed: int | None, res: int) -> None:
    # imports pesados aqui dentro (so quando de fato for gerar)
    import torch
    from diffusers import AutoPipelineForText2Image

    if not torch.cuda.is_available():
        raise SystemExit("[concept] CUDA nao disponivel. Rode na maquina com GPU (venv3d).")

    print(f"[concept] carregando modelo: {model}")
    pipe = AutoPipelineForText2Image.from_pretrained(model, torch_dtype=torch.float16)
    pipe = pipe.to("cuda")

    generator = None
    if seed is not None:
        generator = torch.Generator(device="cuda").manual_seed(seed)

    full_prompt = f"{prompt}, {STYLE_SUFFIX}"
    print(f"[concept] gerando: {full_prompt[:90]}...")
    image = pipe(
        prompt=full_prompt,
        negative_prompt=NEGATIVE,
        num_inference_steps=steps,
        height=res, width=res,
        generator=generator,
    ).images[0]

    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(f"[concept] salvo: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fase 1: texto -> imagem de concept (Stable Diffusion local).")
    ap.add_argument("--prompt", required=True, help="descricao do personagem")
    ap.add_argument("--out", required=True, type=Path, help="PNG de saida")
    ap.add_argument("--size", type=int, default=64, help="tamanho final do sprite (nao afeta a geracao)")
    ap.add_argument("--model", default="stabilityai/sdxl-turbo",
                    help="checkpoint SD (ID do HuggingFace SEM gating, ou caminho local)")
    ap.add_argument("--steps", type=int, default=6, help="passos de difusao")
    ap.add_argument("--res", type=int, default=768, help="resolucao da geracao (concept limpo p/ o 3D)")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    gerar(args.prompt, args.out, args.model, args.steps, args.seed, args.res)


if __name__ == "__main__":
    main()
