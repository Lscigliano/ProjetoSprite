# CRIADOR SPRITES

Gera **spritesheets isométricos de 8 direções** (fundo transparente) para um MMO 2D,
prontos para o **Godot 4**, a partir de um **modelo 3D animado**.

O trabalho de arte é feito por IA; este programa cuida da **engenharia**:
renderiza as 8 direções, dá o look de pixel art, monta a folha e gera o recurso do Godot.

## O caminho completo (visão geral)

```
IA de desenho  ->  IA imagem→3D (nuvem)  ->  Mixamo (rig+animações)  ->  ESTE PROGRAMA  ->  Godot
 (concept)          (modelo .glb)            (andar/atacar/hurt)         (folha+.tres)
```

Por que 3D? Não existe forma de gerar 8 direções + animações a partir de **uma** imagem 2D
com qualidade/consistência de MMO. O 3D é o que garante o mesmo personagem em todos os ângulos.

## Uso (o comando único)

```bash
# a partir de um modelo 3D animado (precisa do Blender instalado):
py criar.py input/hero.glb

# a partir de frames já renderizados (NÃO precisa do Blender):
py criar.py work/hero/render --name hero
```

## Gerador 3D local (opcional, precisa de GPU NVIDIA)

Em vez de sites pagos (Meshy), dá pra ter o "nosso Meshy" rodando **local, grátis e
ilimitado** numa máquina com **GPU NVIDIA** (testado como alvo: RTX 50 / Blackwell).

```bash
# 1) instala o ambiente (venv3d + PyTorch CUDA 12.8 + TripoSR):
instalar_3d.bat

# 2) imagem -> modelo 3D (.obj p/ Mixamo, .glb p/ Blender):
venv3d\Scripts\python src\gerar3d.py --input input\personagem.png --out input\personagem
```

> ⚠️ O passo imagem→3D exige GPU e **ainda não foi testado numa placa** (a série 50 é
> nova e a compilação CUDA pode precisar de ajuste). Rode em casa e reporte os erros.

Saída em `output/`:
- `<nome>.png`  — a folha (grade), fundo transparente
- `<nome>.json` — metadados (célula, animações, direções, fps, loop)
- `<nome>_frames.tres` — recurso `SpriteFrames` pronto pro Godot 4

## Requisitos

- **Python 3.13+** com `Pillow` e `numpy` (`py -m pip install Pillow numpy`)
- **Blender** (só para o passo de render 3D) — https://www.blender.org/download/

## Como funciona por dentro

| Etapa | Arquivo | Precisa de quê |
|---|---|---|
| Render das 8 direções isométricas | `src/render_directions.py` (roda no Blender) | Blender + modelo 3D |
| Look de pixel art | `src/pixelize.py` | Pillow |
| Espelhar diagonais/lado esquerdo | `criar.py` (`mirror_directions`) | Pillow |
| Montar folha + JSON | `src/pack_spritesheet.py` | Pillow |
| Recurso do Godot | `src/godot_export.py` | — |
| Orquestrador (o comando único) | `criar.py` | — |

Só 5 ângulos são renderizados (S, SE, E, NE, N); NW/W/SW são **espelhos horizontais**
de NE/E/SE — economiza render e garante simetria.

## Configuração

Tudo em `config/default.json`: elevação da câmera, direções, animações (fps/loop),
tamanho da célula e parâmetros da pixelização.

## Prompt para a IA de desenho (resumo)

Peça o personagem **de frente, pose A, mãos vazias, sem armas nem acessórios soltos,
fundo branco sólido**. NÃO peça "isométrico" — o ângulo isométrico é gerado aqui, no render 3D.
