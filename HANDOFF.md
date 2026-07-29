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
`py criar.py <TEXTO | imagem.png | modelo.glb | pasta_de_frames> [--size 64] [--elevation 45] [--classe guerreiro|mago|arqueiro]`
→ detecta a entrada e roda as 5 fases → `output/<nome>.png/.json/_frames.tres`.
`--classe` muda a pose de "attack" (arqueiro ganha um arco 3D na mão) — ver seção dedicada.

**Fases:** 1) texto→imagem (SD local) · 2) imagem→3D (TripoSR) · 3) rig+animações
(esqueleto simples + poses codificadas, ver seção "Fase 3" abaixo) · 4) render 8 direções
(Blender via `bpy`) · 5) pixeliza→folha→Godot.

**MARCO — sessão 2026-07-27 (2ª parte): pipeline COMPLETO funcionando de ponta a ponta
pela 1ª vez.** `py criar.py input/<imagem_chibi_pose_A>.png` → `output/<nome>.png` com
**345 frames reais** (6 animações × ~8 direções) numa imagem de personagem chibi de
verdade (armadura, pose A, fundo claro — seguindo os requisitos da seção 3). Todas as 5
fases rodaram numa única invocação, sem intervenção manual.

**Pronto e TESTADO na máquina de casa (RTX 5060 Ti):**
- Fases **1(pulada)–2–3–4–5 completas**: `criar.py input/foto.glb` cobre 4-5 sempre;
  com uma **imagem** de entrada, cobre 2-3-4-5 também (Fase 1/texto segue não testada).
- Fase **2** (imagem→3D, TripoSR) — inferência na GPU (~2-4s por imagem), extração de mesh
  via `torchmcubes` compilado com CUDA real.
- Fase **3** (`src/rig.py`) — **reescrita do zero nesta sessão, funcionando**. Ver seção
  dedicada abaixo — **UniRig e Rigify foram ambos tentados e abandonados**, com os motivos
  documentados, para não repetir a investigação.
- Fases **4 e 5** — render 8 dir + folha + `.tres` Godot, com `bpy` REAL (Blender 5.2.0 LTS).

### Fase 3 (rig + animações) — como funciona hoje, e o que NÃO funcionou

**UniRig: abandonado.** Assume Linux + compilação CUDA nativa frágil (`spconv` sem build
pra CUDA 12.8/13 — issue aberta sem resposta no repo oficial upstream). Mesmo se
compilasse, não faz retargeting de animação — só gera esqueleto+skin.

**Rigify (addon nativo do Blender): tentado a fundo, abandonado.** O auto-rig
(`rigify.metarigs.human.create()` + `bpy.ops.pose.rigify_generate()`) funciona 100%
headless. O **skinning automático também funciona** (`ARMATURE_AUTO` ou
`ARMATURE_ENVELOPE`, pesos reais confirmados nos vertex groups). O problema real: as
constraints `Copy Transforms` que o Rigify usa pra propagar a pose dos controles
(FK/IK) até os ossos de deformação `DEF-*` têm a `influence` controlada por **drivers**
— e esses drivers **não recalculam em modo `--background`** (confirmado com 6+
abordagens diferentes: `depsgraph.update()`, `frame_set`, `view_layer.update()`,
reavaliação manual do driver + escrita forçada na propriedade — nada propaga a pose
inteira até o `DEF-`, mesmo confirmando que os ossos individuais movem corretamente).
Não vale reabrir essa investigação sem uma pista nova (ex.: rodar SEM `--background`,
com janela oculta, é a única rota não testada).

**Solução adotada, funcionando:** esqueleto humanoide **simples e manual** (19 ossos:
pelvis/spine/chest/neck/head, braços e pernas com 3-4 ossos cada, SEM camadas de
controle IK/FK/tweak), construído por `_build_simple_humanoid()` em `src/rig.py`,
escalado e posicionado automaticamente pelo **bounding-box** do mesh (frações fixas da
altura total — calibradas pra proporção chibi: cabeça = 30% da altura). Skinning via
`ARMATURE_AUTO`. Animações (`idle`, `walk`, `attack`, `sit`, `hurt`, `dead`) são
**poses-chave codificadas a mão** via `keyframe_insert` direto nos ossos de deformação
(não mocap/retarget) — decisão consciente pra evitar depender de uma biblioteca externa
de animação e do problema de retargeting entre esqueletos diferentes. Resultado é mais
"jogo indie" que mocap realista, mas é 100% confiável e roda headless sem workarounds.

**Bug real também corrigido nesta sessão:** o `.glb` que o TripoSR exporta vem **deitado**
(não Z-up) — o objeto pai (`Empty`) usa `rotation_mode='QUATERNION'`, então setar
`rotation_euler` nele é um no-op silencioso (armadilha real, gastou bastante tempo de
depuração). Fix em `_normalize_triposr_orientation()`: aplicar
`Quaternion((0,0,1), 90°) @ Quaternion((1,0,0), -90°)` via `rotation_quaternion` no
objeto pai antes de "achatar" a transformação no mesh. Confirmado consistente em 2
modelos diferentes (personagem chibi + raposa de exemplo do TripoSR).

**Arquitetura de venvs (importante, já corrigida em `criar.py`):** `src/rig.py` agora só
precisa de `bpy` (não de GPU/torch), então `criar.py.run_rig()` chama o Python do
**`venv_bpy`** (3.13), não do `venv3d` (3.12, onde fica o TripoSR) — são dois venvs
diferentes por causa da versão de Python exigida por cada wheel.

**Bug real corrigido (personagem minúsculo na célula do sprite):** toda vez que o
Blender **reimporta** um `.glb` com armature sem custom shapes de bone (nosso caso — rig
manual, sem widgets), ele cria automaticamente um objeto `Icosphere` genérico (~2×2×2
unidades) como placeholder visual — **maior que o próprio personagem** (que tem ~1m de
altura). Esse objeto poluía o cálculo de bounding-box em `render_directions.py`
(`_scene_bounds`), fazendo a câmera se afastar demais → personagem pequeno na célula.
**Não está no `.glb` salvo** (confirmado inspecionando o JSON chunk cru do arquivo) — só
aparece a cada reimportação, então qualquer script que reabra o `.glb` precisa filtrar.
Fix: `_remove_gltf_joint_placeholders()` em `render_directions.py`, chamado logo após
`bpy.ops.import_scene.gltf`, remove objetos `MESH` chamados exatamente `"Icosphere"` sem
vertex groups (nunca é o mesh real do personagem).

Aproveitado para também corrigir o cálculo de `ortho_scale` da câmera (`_setup_camera`):
antes usava só a altura Z do personagem; agora calcula a altura **aparente na tela**
considerando a elevação de 45° E a extensão horizontal (já que o personagem gira em Z
durante o render — qualquer lado pode ficar de frente pra câmera). Fórmula:
`altura_aparente = altura*sin(elev) + 2*raio_horizontal*cos(elev)`, com 15% de margem.
Validado por simulação numérica da projeção real em todos os azimutes (erro <3% vs a
fórmula fechada) — ver histórico do commit se precisar re-derivar.

### Bug real (personagem saía cinza/sem cor) — 2 causas empilhadas, ambas corrigidas

Depois do checkpoint acima, o usuário notou o personagem gerado saindo **cinza**, sem a
cor real da imagem de origem (roupa verde, pele etc.). Duas causas distintas, as duas
precisavam ser corrigidas juntas:

1. **`AgX` (color management padrão do Blender 4+/5) dessatura MUITO o vertex color do
   TripoSR** — em EEVEE/Cycles o personagem saía cinza-lavado mesmo com boa iluminação e
   a cor de fato presente no mesh (confirmado lendo o `Color Attribute` direto). Só o
   Workbench "escapava" disso (usa Studio Light fixo, ignora color management). **Fix**:
   `scene.view_settings.view_transform = "Standard"` em `_setup_render()` — sem
   tonemapping, mostra a cor real. Se um dia quiser um look mais "cinematográfico", isso
   é o primeiro lugar a mexer (mas cuidado, é fácil voltar a dessaturar sem perceber).
2. **Resolução de render abaixo de ~200px perde a cor quase inteira** (confirmado
   varrendo 64/96/128/192/256/300px na mesma cena: 128px = cinza quase puro, 300px =
   cor nítida). Hipótese: com o personagem ocupando poucos pixels na tela, o
   antialiasing do EEVEE mistura a cor de vertex-color com a vizinhança e "borra" pro
   cinza médio. **Não é bug de código, é physically-based**: o `--resolution` (default
   **512**, em `criar.py`) já é bem acima do limiar — só apareceu porque testes manuais
   desta sessão usavam `--resolution 128/192` pra acelerar. **Regra prática: nunca passar
   `--resolution` abaixo de ~256 se a cor importa** (o `pixelize.py` já faz o downscale
   de qualidade pro tamanho final do sprite depois, não precisa renderizar pequeno).

Também existe (raro, intermitente, causa não 100% isolada) um bug real do **reimportador**
glTF do Blender 5.2: às vezes, ao reabrir um `.glb` cujo mesh tem tanto `COLOR_0`
(vertex color) quanto `JOINTS_0`/`WEIGHTS_0` (skinning), o Blender falha em reconstruir o
`Color Attribute`/material da cena — **mesmo o arquivo `.glb` tendo os dados corretos**
(confirmado lendo o binário do glTF direto via `struct`/`json`, sem depender do bpy).
Não achei o gatilho exato (não é sobre `export_animations`, `export_force_sampling`,
`export_apply`, nem sobre `material_slot.link`), e não é 100% reprodutível — às vezes o
reimport funciona normal, às vezes não, com o mesmo código. **Mitigação defensiva**:
`_recover_vertex_color_from_glb()` em `render_directions.py`, chamada logo após todo
`import_scene.gltf` de `.glb` — se detectar que o mesh reimportado não tem
`color_attributes` (sinal do bug), lê o accessor `COLOR_0` bruto do arquivo `.glb` e
recria o `Color Attribute` + material manualmente. Roda em ~1ms mesmo quando não é
necessária (early-return se `color_attributes` já existir), então é seguro deixar sempre
ativa. Se um dia esse bug do Blender for corrigido upstream, essa função vira no-op.

### Sistema de classes (`--classe guerreiro|mago|arqueiro`) — pedido do dono

`criar.py --classe <nome>` (default `guerreiro`) muda a pose da animação `attack` — as
outras 5 (idle/walk/sit/hurt/dead) são compartilhadas entre classes, já que não dependem
de arma. Implementado em `_apply_animations(bpy, rig, classe=...)` em `src/rig.py`:
- **guerreiro** (padrão): golpe genérico de braço direito, recua e avança.
- **mago**: os dois braços sobem e se aproximam na frente do peito (gesto de "canalizar"),
  sem nenhum objeto anexado — a "arma" de um mago é visual/efeito, não modelo 3D por ora.
- **arqueiro**: braço esquerdo sustenta um arco parado e esticado pra frente, braço
  direito puxa a corda até o ombro e solta. **Só essa classe ganha um objeto 3D real**
  (um arco simples, ver abaixo).

**Arco do arqueiro — como funciona e o que ficou pendente:**
`_add_bow_geometry()` cria um arco (curva bezier convertida em malha, ~35% da altura do
personagem, curvatura leve) posicionado na MESMA fórmula de coordenadas que
`_build_simple_humanoid` usa pra `hand.L` (`_body_geometry()` foi extraída como função
compartilhada pra garantir isso). Chamado **antes** do rig+skin em `build_rig()`, o arco é
**fundido (`bpy.ops.object.join()`) na malha do personagem**, não parenteado como objeto
separado — decisão forçada por um bug real: `bpy.ops.object.parent_set(type="BONE")`
calculava uma `matrix_parent_inverse` que não correspondia à posição real do osso (a
malha do arco terminava sempre perto da origem do mundo, não na mão), e não foi possível
isolar a causa raiz mesmo depurando passo a passo (matrizes conferidas, contexto/seleção
confirmados corretos). Fundindo antes do skin, o arco ganha peso de vértice automático
pelo `ARMATURE_ENVELOPE` — resultado: **o arco agora segue a mão corretamente durante a
animação** (confirmado visualmente no frame de "puxar a corda").

**Pendência conhecida:** a cor do arco sai parcialmente errada — parte da malha aparece
marrom (correto) e parte preta. Tentado: pintar um `Color Attribute` próprio no arco antes
do join (a cor pintada foi confirmada correta em memória em cada etapa: após pintura, após
join, após skin — mas vira branco/preto após export+reimport, mesmo padrão inconsistente
do bug de material já documentado acima). Não vale mais tempo agora — funcionalmente o
arco funciona (segue a mão, aparece, tem forma de arco); é só um acabamento visual.

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
