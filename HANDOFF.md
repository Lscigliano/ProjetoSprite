# HANDOFF / CONTEXTO DO PROJETO — para a próxima IA (Claude Code, Codex, etc.)

> Leia este arquivo inteiro antes de agir. Ele resume o objetivo, as decisões já
> tomadas (e o **porquê**), os requisitos que o usuário deve seguir, o que já está
> pronto/testado e o que falta. Assim você não repete discussões nem quebra o que funciona.
> Veja também **ARQUITETURA.md** (blueprint) e **INSTALACAO_CASA.md** (setup passo a passo).

---

## ⭐ CHECKPOINT (estado atual — leia primeiro)

**O que é:** ferramenta "PixelLab caseiro" — **local, grátis, sem login/conta** — que gera
**spritesheets 8 direções** (estilo **Ragnarok Online**) pro **Godot 4**. Alvo: MMO 2D isométrico.

**Como usar (um comando, 4 tipos de entrada):**
`py criar.py <TEXTO | imagem.png | modelo.glb | pasta_de_frames> [--size 64] [--elevation 45]`
→ detecta a entrada e roda as 5 fases → `output/<nome>.png/.json/_frames.tres`.

**Fases:** 1) texto→imagem (SD local) · 2) imagem→3D (TripoSR) · 3) rig+animações (UniRig)
· 4) render 8 direções (Blender via `bpy`) · 5) pixeliza→folha→Godot.

**Pronto e TESTADO na máquina de casa (RTX 5060 Ti), sessão 2026-07-27:**
- Fases **4 e 5** (render 8 dir + folha + `.tres` Godot) — `py tests/testar_pipeline.py` passa,
  agora com `bpy` REAL (Blender 5.2.0 LTS), não só simulado como na sessão anterior.
- Fase **2** (imagem→3D, TripoSR) — **VALIDADA de ponta a ponta**: `gerar3d.py` gera `.obj`+`.glb`
  reais a partir de uma imagem (testado com `third_party/TripoSR/examples/poly_fox.png`).
  `torch.cuda.is_available() == True`, inferência na GPU (~2s), extração de mesh via
  `torchmcubes` compilado com CUDA real (~1.5s).
- Câmera 45° (estilo RO), ajustável por `--elevation` (45–60). Workbench já sai com textura/cor.
- Ações no `config`: idle, walk, attack, sit, hurt, dead × 8 direções.

**AINDA escrito mas NÃO testado:**
- `src/gerar_concept.py` (Fase 1, Stable Diffusion) — scaffold, ajustar checkpoint. Não mexido
  nesta sessão (foco foi Fase 2).
- `src/rig.py` (Fase 3, UniRig) — **o gargalo aberto, ainda não atacado**: o auto-rig é chamada
  externa a confirmar no README do UniRig, e o **retargeting das animações mocap ainda NÃO foi
  resolvido**. Confirmado nesta sessão: um `.glb` do TripoSR não tem nenhuma `Action`
  (idle/walk/etc.) — é só geometria estática — então a Fase 4 roda mas não renderiza nada até
  a Fase 3 existir de verdade.

### Setup de ambiente desta máquina (casa) — registrar p/ não repetir a depuração

Ambiente veio "zerado" (só driver NVIDIA, sem CUDA Toolkit/Python 3.13). Passos que foram
necessários e NÃO estavam no HANDOFF anterior:

1. **Python 3.13 via winget** (`Python.Python.3.13`) — só existe wheel de `bpy` pro cp313, não
   pro Python 3.12 que já estava instalado. `venv_bpy/` (Python 3.13) é o ambiente usado pelas
   Fases 4-5 (`criar.py`, `tests/testar_pipeline.py`). `venv3d/` (o do `instalar_3d.bat`, Python
   3.12 — versão base desta máquina) é o ambiente da Fase 2 (`gerar3d.py`/TripoSR). São DOIS
   venvs por causa da versão de Python exigida por cada wheel — isso é esperado, não confundir.
2. **CUDA Toolkit via winget** (`Nvidia.CUDA`, instalou 13.3 — não existe 12.8 no winget hoje;
   13.3 funcionou bem com a RTX 5060 Ti). Só o *driver* NVIDIA (`nvidia-smi`) NÃO basta — o
   `torchmcubes` (dependência do TripoSR) precisa compilar C++/CUDA e exige o toolkit completo
   (`nvcc`) instalado à parte. O instalador pede UAC (elevação) — se rodar via automação/CLI,
   avisar o dono pra aprovar o prompt.
   - Depois de instalar, a sessão de terminal ABERTA ANTES não pega `CUDA_PATH`/`CUDA_PATH_V13_3`
     automaticamente (ficam só a nível de máquina/registro) — setar manualmente na sessão atual
     (`$env:CUDA_PATH`, `$env:CUDA_PATH_V13_3`) antes de instalar pacotes que compilam CUDA.
3. **Bug de compilação real (CCCL/MSVC muito novo)**: build do `torchmcubes` falhava com
   `fatal error C1189: MSVC/cl.exe with traditional preprocessor is used` mesmo com CUDA/nvcc
   corretos. Causa: MSVC 19.51 (Visual Studio 18, versão desta máquina) exige o preprocessador
   conforme-padrão pro CCCL/CUB novo do CUDA 13.3. **Fix**: setar
   `$env:NVCC_APPEND_FLAGS = "-Xcompiler /Zc:preprocessor"` antes do `pip install`. Sem isso o
   build falha sempre nessa combinação de versões.
4. **Bug de versão numpy/trimesh**: `TripoSR/requirements.txt` pina `trimesh==4.0.5` (2023), que
   quebra com `numpy>=2.0` (`AttributeError: 'numpy.ndarray' object has no attribute 'ptp'` ao
   exportar `.glb`). **Fix**: `pip install -U trimesh` (testado com 4.12.2) — o `gerar3d.py` só
   usa trimesh pra exportar formato, uma versão nova é segura.
5. **`gradio` foi OMITIDO** do install de `third_party/TripoSR/requirements.txt` de propósito —
   é dependência só da demo web (`gradio_app.py`), não do `run.py` que `gerar3d.py` chama, e
   instalar junto causa um backtracking gigante do pip (resolvendo ~150 versões de gradio) sem
   necessidade. Se um dia precisar da demo web do TripoSR, instalar `gradio` à parte.

**Onde parou / próximo passo:** Fases 2, 4 e 5 validadas nesta máquina com GPU real. O próximo
trabalho é **a Fase 3 (rig + retarget de animação)** — ainda não atacada, é o gargalo real que
falta pra fechar o pipeline completo (texto/imagem → sprite ANIMADO). Rode
`py verificar_ambiente.py` pra conferir o estado do ambiente a qualquer momento (nota: esse
script hoje só checa o Python "base" do `py`, não os dois venvs — pode reportar `bpy`/`trimesh`
como faltando mesmo já instalados nos venvs certos; conferir os venvs diretamente se isso confundir).

---

## 1. Quem é o usuário e o que ele quer
- **Usuário:** analista/desenvolvedor, **não é desenhista**. Toda a ARTE deve vir de **IA/ferramentas automáticas**; ele cuida do código/integração.
- **Objetivo:** um **MMO 2D isométrico independente**. Precisa de **spritesheets de personagens** com qualidade, **fundo transparente**, **8 direções** e animações (idle, andar, atacar com flecha, levar dano/hurt).
- **Princípio inegociável:** o programa tem que ser **SIMPLES** — "jogar a entrada X e sair o resultado Y" com **um comando só**. Nada de obrigar o usuário a orquestrar vários scripts.
- **Engine de destino:** **Godot 4**.

## 2. Decisão de arquitetura (e o PORQUÊ) — não reabrir sem motivo
O usuário sonhava em "dar 1 imagem 2D e o programa gerar as 8 direções + animações".
**Isso é impossível** com qualidade/consistência de MMO, porque:
1. Uma imagem de frente **não contém** as costas/lados (informação inexistente).
2. IA de imagem **não mantém o mesmo personagem** consistente em ~130 quadros.

**Caminho adotado (o que funciona): 3D pré-renderizado.**
```
concept (IA de desenho) -> imagem->3D -> rig+animações (Mixamo) -> render 8 direções (Blender)
                                                                 -> pixeliza -> monta folha -> Godot
```
O 3D é o que garante 8 direções + o MESMO personagem em todos os ângulos.

## 3. REQUISITOS DA ARTE (o que o usuário deve pedir à IA de desenho)
Estes requisitos foram definidos para a reconstrução 3D funcionar. **Reforce-os:**
- **Vista de FRENTE**, personagem **centralizado**, **fundo branco sólido**.
- **Pose em "A"**: braços retos e **afastados do corpo**, **mãos abertas e vazias**.
- **SEM armas** e **SEM acessórios soltos** (nada de arco, flechas, aljava, bolsas,
  alças cruzadas, capa, cachecol) — isso **quebra o 3D**. Armas entram DEPOIS como peça separada.
- Armadura/capacete/luvas/botas coladas ao corpo = OK.
- Estilo **chibi** (cabeça grande) — lê melhor no isométrico.
- ❌ **NÃO** pedir "isométrico" à IA de desenho — o ângulo isométrico é gerado no
  render 3D (Blender). Pedir isométrico no desenho atrapalha o 3D.
- Cabelo muito longo/solto pode "borrar" no 3D (aviso menor).

## 4. Hardware
- **Máquina de trabalho** (onde o código foi escrito): **SEM GPU** e com **AppLocker**
  (política corporativa) que **bloqueia executar .exe** de pastas do usuário/Temp.
  → Solução descoberta: rodar o Blender como **módulo Python `bpy`** (`pip install bpy`),
    que executa dentro do `python.exe` (permitido). O render funciona MESMO aqui, sem admin.
- **Máquina de casa** (onde vai rodar de verdade): **Ryzen 5 7600X + RTX 5060 Ti** (série 50 / Blackwell).
  - Exige **PyTorch CUDA 12.8+** (versões antigas não reconhecem a placa).
- **Regra do usuário:** pode usar qualquer ferramenta/modelo, mas **sem login/conta** (nada de Meshy/Mixamo).

## 5. O que já está PRONTO e TESTADO ✅
Rodado de ponta a ponta com frames sintéticos (sem GPU/Blender) e validado:
- `criar.py` — **comando único**. Faz: (render) → pixeliza → **espelha diagonais** → monta folha → export Godot.
- `src/pixelize.py` — look de pixel art (reduz resolução + paleta + alpha nítido).
- `src/pack_spritesheet.py` — monta a folha (grade) + `JSON` de metadados.
- `src/godot_export.py` — gera `SpriteFrames .tres` do **Godot 4** (formato validado).
- Demo verificada em `output/teste.png|json|tres` (2 anims × 8 direções).
- **Truque das direções:** só 5 ângulos são renderizados (S, SE, E, NE, N);
  **NW/W/SW são espelhos horizontais** de NE/E/SE (ver `config/default.json`).
- `src/render_directions.py` — render das 8 direções isométricas. **VALIDADO** nesta
  máquina (sem GPU) via o módulo **`bpy`** (`pip install bpy`) + motor Workbench,
  gerando a folha do Fox em 8 direções (walk). Roda como script Python normal
  (`py src/render_directions.py ...`) OU dentro do Blender.exe.
- **Teste reproduzível:** `py tests/testar_pipeline.py` (baixa um modelo CC0 e valida tudo).
- **Passo a passo de instalação em casa:** ver **`INSTALACAO_CASA.md`**.

## 6. O que está ESCRITO mas NÃO testado ⏳ (precisa da máquina de casa)
- ~~`render_directions.py` nunca rodou~~ → **JÁ VALIDADO** (ver seção 5). Movido para "pronto".
- `instalar_3d.bat` — cria `venv3d`, instala **PyTorch cu128** e o **TripoSR** (imagem→3D).
  **Não testado em GPU**; a compilação CUDA da série 50 pode falhar e precisar de ajuste.
- `src/gerar3d.py` — wrapper **imagem→3D** (saída `.obj` p/ Mixamo, `.glb` p/ Blender).
  Só o "esqueleto" da orquestração foi revisado; o passo do TripoSR depende da instalação com GPU.

## 7. Como rodar (resumo)
```bash
# instalar dependencias (inclui bpy = Blender via pip, sem app/admin):
py -m pip install -r requirements.txt

# pipeline principal a partir de um modelo 3D animado (usa o modulo bpy):
py criar.py input/hero.glb

# a partir de frames já renderizados (NÃO precisa de Blender):
py criar.py work/hero/render --name hero

# gerador imagem->3D local (só na máquina com GPU):
instalar_3d.bat
venv3d\Scripts\python src\gerar3d.py --input input\personagem.png --out input\personagem
```
Config central: `config/default.json` (câmera, 8 direções, animações fps/loop, pixelize, célula).

## 8. PRÓXIMOS PASSOS (onde continuar)
1. **[EM CASA]** rodar `instalar_3d.bat` e validar `torch.cuda.is_available()` na RTX 5060 Ti.
   Se a compilação (ex.: `torchmcubes`) falhar, ajustar versões — este é o 1º risco real.
2. **[EM CASA]** gerar o 1º `.glb` com `gerar3d.py` a partir do concept chibi (ou usar Tripo3D/3D AI Studio como atalho grátis).
3. Rig + animações no **Mixamo** (nomear as actions: `idle`, `walk`, `attack`/shoot, `hurt` —
   o `render_directions.py` casa a animação pelo nome, substring case-insensitive).
4. Instalar **Blender**, rodar `py criar.py input/hero.glb` e **testar o render real** (1º teste de verdade do Blender).
5. Ajustar câmera/tamanho/paleta conforme o resultado.
6. Criar o **arco como asset separado** (arma trocável no MMO).

## 9. Armadilhas conhecidas / lições
- Não prometer "1 imagem → folha completa" (impossível; ver seção 2).
- **Meshy** gera de graça mas **trava o download** (paywall). Alternativas grátis com
  download liberado: **Tripo3D**, **3D AI Studio** (100 créditos/mês). **MeshConvert.com NÃO serve**
  (só converte formato de 3D existente, não faz imagem→3D).
- Mixamo aceita `.obj`/`.fbx` (não `.glb`) para upload; por isso `gerar3d.py` também exporta `.obj`.
- Chibi tem membros curtos → o **auto-rig do Mixamo** pode se atrapalhar; pode exigir ajuste manual.

---
_Checkpoint neste commit: pipeline base pronto e testado; módulo 3D e render Blender
escritos, aguardando teste na máquina com GPU (casa)._
