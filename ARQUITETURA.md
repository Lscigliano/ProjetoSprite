# ARQUITETURA — "PixelLab caseiro" (local, grátis, sem conta)

## Visão
Uma ferramenta **nossa** que faz o que a PixelLab faz, mas **100% local, grátis e sem login**:
a partir de **texto/atributos** (ou uma imagem), gerar um **sprite sheet animado em 8 direções**
(estilo Ragnarok), pronto pro Godot.

**Como isso é possível sem treinar um modelo do zero:** nós NÃO treinamos uma IA nova
(isso exigiria dataset + cluster de GPU + tempo de empresa). Nós **orquestramos modelos
open-source que já existem** (o "combustível") com o nosso código (o "motor"). Cada peça
roda local, baixada sem conta.

## Fluxo de dados (as fases)
```
[texto / atributos]                 ex.: "urso guerreiro chibi, armadura laranja"
   │  FASE 1 — concept (opcional)   Stable Diffusion + LoRA pixel art  (local, GPU)
   ▼
[imagem PNG do personagem]          (ou VOCÊ fornece a imagem pronta)
   │  FASE 2 — imagem -> 3D         Hunyuan3D / TripoSR  (local, GPU)     src/gerar3d.py
   ▼
[modelo 3D .glb]
   │  FASE 3 — rig + animações      UniRig / Blender Rigify + mocap CC0   src/rig.py  (a fazer)
   ▼                                (idle, walk, attack, sit, hurt, dead)
[modelo 3D ANIMADO]
   │  FASE 4 — render 8 direções    Blender via módulo bpy                src/render_directions.py
   ▼
[frames PNG por ação/direção]
   │  FASE 5 — pixeliza + espelha + monta folha + Godot   pixelize / pack / godot_export
   ▼
[spritesheet.png + .json + .tres do Godot]
```
Por que 3D no meio? É o que garante **8 direções idênticas** + **qualquer pose** (como o
Ragnarok fez). É a espinha dorsal mais confiável para consistência.

## Status de cada peça
| Fase | Módulo | Estado |
|---|---|---|
| 1. Concept (texto→imagem) | ComfyUI + SD + LoRA (a integrar) | ⏳ a implementar (opcional) |
| 2. Imagem→3D | `src/gerar3d.py` (TripoSR) | ✍️ escrito — testar na GPU (casa) |
| 3. Rig + animações | `src/rig.py` | ❌ **a fazer — é o gargalo** |
| 4. Render 8 direções | `src/render_directions.py` (bpy) | ✅ **VALIDADO** (Fox) |
| 5. Folha + JSON + Godot | `pixelize` / `pack_spritesheet` / `godot_export` | ✅ **pronto e testado** |
| Orquestrador | `criar.py` | ✅ cobre fases 4–5; integrar 1–3 |

## Modelos open-source usados (todos sem conta)
- **Stable Diffusion** (+ LoRA de pixel art) — concept art. Via **ComfyUI** local.
- **Hunyuan3D / TripoSR** — imagem→3D. Pesos no HuggingFace (download sem login).
- **UniRig** (SIGGRAPH 2025) ou **Blender Rigify** — esqueleto automático.
- **Quaternius / Truebones (CC0)** — biblioteca de animações mocap grátis.
- **Blender (módulo `bpy`)** — render.

## Roadmap
1. ✅ Fases 4 e 5 (render + montagem) — feito e validado nesta máquina.
2. ⏳ **[EM CASA/GPU]** Fase 2: rodar `gerar3d.py`, validar imagem→3D.
3. ❌ **[EM CASA/GPU]** Fase 3: `rig.py` — auto-rig + aplicar animações CC0. **Prioridade.**
4. ⏳ **[EM CASA/GPU]** Fase 1: front-end de texto (ComfyUI/SD) — opcional, por último.
5. Unir tudo no `criar.py`: `py criar.py "texto do personagem"` → sprite sheet.

## Expectativa honesta
- ✅ Alcançável: uma ferramenta **livre, local, sua**, que entrega sprites **usáveis** pro seu MMO.
- ❌ Não prometido: **superar** a PixelLab (produto de empresa, anos de foco). O nosso diferencial
  não é ser "melhor" — é ser **independente, grátis e 100% seu**.
- O elo mais difícil e ainda aberto é a **Fase 3 (rig)**. Depende de teste na GPU de casa.
