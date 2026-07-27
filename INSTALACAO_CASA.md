# INSTALAÇÃO EM CASA — passo a passo (para IA ou humano)

> Máquina de casa: **Ryzen 5 7600X + RTX 5060 Ti (série 50 / Blackwell)**, Windows.
> Regra do projeto: **sem login/conta em serviços**. Tudo roda local; só baixamos
> ferramentas/modelos open-source (não exige e-mail/senha).

O projeto tem **duas partes**:
- **A) Pipeline de sprite** (render → pixeliza → folha → Godot) — **NÃO precisa de GPU**. Já validado.
- **B) Geração de arte por IA** (concept, imagem→3D, rig) — **precisa da GPU**. A testar em casa.

---

## Pré-requisitos
1. **Python 3.13** (https://www.python.org/downloads/ — marque "Add to PATH").
2. **Git** (https://git-scm.com/download/win).
3. Placa **NVIDIA** com driver atual (só para a Parte B).

## Passo 0 — pegar o projeto
```bat
git clone https://github.com/Lscigliano/ProjetoSprite.git
cd ProjetoSprite
```

---

## PARTE A — Pipeline de sprite (sem GPU) — JÁ FUNCIONA
```bat
py -m pip install -r requirements.txt
```
Isso instala `Pillow`, `numpy`, `trimesh` e o **`bpy`** (Blender como módulo Python —
renderiza headless **sem precisar instalar o app Blender nem ser admin**).

**Testar** (baixa um modelo CC0 e roda tudo de ponta a ponta):
```bat
py tests\testar_pipeline.py
```
Se aparecer "OK! folha=..., 8 direcoes", a Parte A está 100%.

**Usar** (quando você tiver um modelo 3D animado `.glb`/`.fbx`):
```bat
py criar.py input\meu_personagem.glb
```
Em casa, para qualidade melhor troque o motor (EEVEE usa a GPU):
```bat
py criar.py input\meu_personagem.glb --engine BLENDER_EEVEE_NEXT
```
Saída em `output\`: `.png` (folha, fundo transparente), `.json` e `_frames.tres` (Godot 4).

---

## PARTE B — Geração de arte por IA (precisa da RTX 5060 Ti)

### B1) Concept art — Stable Diffusion local
- Instale **ComfyUI** (https://github.com/comfyanonymous/ComfyUI) — open-source, roda local, sem conta.
  (Baixe o "portable" do Windows OU clone + `pip install -r requirements.txt`.)
- Baixe um checkpoint (ex.: SDXL) de um repositório aberto e coloque em `ComfyUI\models\checkpoints`.
- Gere o personagem com o prompt do HANDOFF (frente, pose A, mãos vazias, sem
  acessórios, fundo branco, chibi). Salve o PNG.

### B2) Imagem → 3D — TripoSR local
```bat
instalar_3d.bat
```
Esse script cria `venv3d`, instala **PyTorch com CUDA 12.8** (obrigatório p/ série 50) e o **TripoSR**.
> ⚠️ **1º risco real:** a compilação CUDA (ex.: `torchmcubes`) pode falhar na série 50.
> Se der erro, copie a mensagem e ajustamos (geralmente é versão de toolkit/wheel).

Testar a GPU:
```bat
venv3d\Scripts\python -c "import torch;print('CUDA:',torch.cuda.is_available(),torch.cuda.get_device_name(0))"
```
Gerar o 3D a partir do PNG:
```bat
venv3d\Scripts\python src\gerar3d.py --input input\personagem.png --out input\personagem
```
Gera `input\personagem.obj` (p/ rig) e `input\personagem.glb`.

### B3) Rig + animações — o passo mais difícil (local, sem conta)
Precisamos de esqueleto + animações (idle/walk/attack/hurt) SEM Mixamo (Mixamo exige conta Adobe).
Opções locais (a decidir/testar em casa):
- **UniRig** (SIGGRAPH 2025, open-source, auto-rig por IA; modelos no HuggingFace, sem login):
  https://github.com/VAST-AI-Research/UniRig  → gera esqueleto + skinning do mesh.
- **Blender + Rigify** (manual) + **arquivos de animação CC0** (ex.: mocap da CMU em BVH),
  com retarget dentro do Blender.
- As animações precisam existir como CLIPES (mocap CC0 baixado, sem conta) e ser aplicadas ao rig.
> Este passo ainda **não foi implementado nem testado**. É o próximo grande trabalho.

### B4) Fechar o ciclo
Com o `.glb` **animado** pronto:
```bat
py criar.py input\personagem_animado.glb --engine BLENDER_EEVEE_NEXT
```
→ folha isométrica 8 direções pronta pro Godot.

---

## Resumo do que instalar em casa
| Item | Como | Precisa GPU? | Conta? |
|---|---|---|---|
| Python 3.13, Git | instaladores oficiais | não | não |
| Pipeline sprite (`requirements.txt`, inclui `bpy`) | `pip install -r requirements.txt` | não | não |
| ComfyUI + checkpoint (concept) | download open-source | sim | não |
| PyTorch CUDA 12.8 + TripoSR (imagem→3D) | `instalar_3d.bat` | sim | não |
| UniRig / Rigify + mocap CC0 (rig) | download open-source | sim (UniRig) | não |

## Estado atual (o que já está provado)
- ✅ Parte A validada nesta máquina de trabalho (sem GPU) via `bpy`, gerando folha 8 direções.
- ⏳ Parte B escrita/planejada; falta rodar/testar na máquina com GPU (casa).
