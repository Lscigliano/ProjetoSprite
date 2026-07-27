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

**Pronto e TESTADO** (roda sem GPU, validado com o modelo CC0 Fox):
- Fases **4 e 5** (render 8 dir + folha + `.tres` Godot). `py tests/testar_pipeline.py` passa.
- Render via **`pip install bpy`** (driblou o AppLocker da máquina de trabalho — sem app, sem admin).
- Câmera **45°** (estilo RO), ajustável por `--elevation` (45–60). Workbench já sai com textura/cor.
- Ações no `config`: idle, walk, attack, sit, hurt, dead × 8 direções.

**Escrito mas NÃO testado (precisa da GPU de casa — RTX 5060 Ti):**
- `src/gerar_concept.py` (Fase 1, Stable Diffusion) — scaffold, ajustar checkpoint.
- `src/gerar3d.py` (Fase 2, TripoSR) — instalar via `instalar_3d.bat`.
- `src/rig.py` (Fase 3, UniRig) — **o gargalo aberto**: o auto-rig é chamada externa a
  confirmar no README do UniRig, e o **retargeting das animações mocap ainda NÃO foi resolvido**.

**Onde parou / próximo passo:** tudo que não é GPU está pronto e no GitHub
(github.com/Lscigliano/ProjetoSprite). O próximo trabalho é **na máquina de casa (GPU)**:
rodar `instalar_3d.bat`, validar Fases 1–2, e atacar a **Fase 3 (rig + retarget)** — o elo faltante.
Rode `py verificar_ambiente.py` na máquina de casa para ver o que falta instalar.

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
