# TASK — CRIADOR SPRITES

## Objetivo
Programa simples ("jogar entrada X → sai o spritesheet Y") que gera spritesheets
isométricos 8-direções, fundo transparente, prontos pro Godot 4, para um MMO 2D.

## Arquitetura decidida
Pipeline 3D→sprite: concept (IA) → imagem-para-3D (nuvem) → Mixamo (rig/animações)
→ **este programa** (render Blender → pixeliza → espelha → monta folha → export Godot).

## Checklist
- [x] Dependências Python (Pillow, numpy)
- [x] Config (`config/default.json`) — câmera, 8 direções, animações, pixelize, sheet
- [x] `src/pixelize.py` — look de pixel art (reduz resolução + paleta + alpha nítido)
- [x] `src/pack_spritesheet.py` — monta a folha (grade) + JSON de metadados
- [x] `src/godot_export.py` — gera `SpriteFrames .tres` (Godot 4)
- [x] `src/render_directions.py` — render 8 direções isométricas no Blender (headless)
- [x] `criar.py` — comando único de ponta a ponta (+ espelhamento das diagonais)
- [x] Verificação com frames sintéticos → `output/teste.*` gerado e validado
- [ ] Teste real com Blender + modelo 3D (pendente: instalar Blender + ter o .glb)

## Review (o que foi feito)
- Pipeline roda de ponta a ponta SEM Blender quando os frames já existem
  (`py criar.py <pasta_de_frames>`), o que permitiu testar tudo hoje.
- Teste sintético: 2 animações × 8 direções → folha 256×1024, `.json` e `.tres`
  validados (formato Godot 4 correto, espelhamento e transparência OK).
- Só o passo de RENDER depende de Blender + modelo 3D (ainda não instalados/gerados).

## Módulo 3D local (para a máquina de casa: Ryzen 5 7600X + RTX 5060 Ti)
- [x] `instalar_3d.bat` — venv3d + PyTorch CUDA 12.8 (Blackwell) + TripoSR
- [x] `src/gerar3d.py` — wrapper imagem→3D (saída .obj p/ Mixamo, .glb p/ Blender)
- [ ] **[EM CASA]** testar instalação na GPU (compilação CUDA pode precisar de ajuste)
- [ ] **[EM CASA]** validar imagem→3D com o personagem real

## Próximos passos
1. Usuário gera o concept na IA (front, pose A, mãos vazias, sem acessórios, fundo branco).
2. Converter concept → modelo 3D:
   - rápido: Tripo3D / 3D AI Studio (nuvem, grátis); ou
   - próprio: `instalar_3d.bat` + `gerar3d.py` na máquina de casa (GPU).
3. Rig + animações no Mixamo (nomear actions: idle/walk/attack/hurt).
4. Instalar Blender e rodar `py criar.py input/hero.glb`.
5. Encaixar arco como asset separado (arma trocável no MMO).
