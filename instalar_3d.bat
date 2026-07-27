@echo off
REM ============================================================
REM  CRIADOR SPRITES - instalador do modulo imagem->3D (local, GPU)
REM  Alvo: Windows + NVIDIA RTX 50 (Blackwell) -> PyTorch CUDA 12.8
REM ------------------------------------------------------------
REM  IMPORTANTE (honesto): este script NAO foi testado numa GPU.
REM  A serie 50 e nova; se der erro de compilacao (ex.: torchmcubes),
REM  copie a mensagem e me mande que a gente ajusta na hora.
REM ============================================================
setlocal

echo.
echo === [1/5] Verificando Python ===
py --version || (echo Python nao encontrado & goto :fim)

echo.
echo === [2/5] Criando ambiente virtual venv3d ===
if not exist venv3d (
    py -m venv venv3d
) else (
    echo venv3d ja existe, reutilizando.
)
call venv3d\Scripts\activate.bat

echo.
echo === [3/5] Atualizando pip ===
python -m pip install --upgrade pip

echo.
echo === [4/5] Instalando PyTorch com CUDA 12.8 (RTX 50 / Blackwell) ===
REM Se sua placa fosse serie 40, trocaria cu128 por cu121.
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

echo.
echo === [5/5] Instalando dependencias do gerador 3D ===
pip install rembg onnxruntime pillow numpy trimesh huggingface_hub einops omegaconf transformers

echo.
echo === Baixando o TripoSR (backend imagem->3D leve) ===
if not exist third_party\TripoSR (
    git clone https://github.com/VAST-AI-Research/TripoSR third_party\TripoSR
)
if exist third_party\TripoSR\requirements.txt (
    pip install -r third_party\TripoSR\requirements.txt
)

echo.
echo ============================================================
echo  Instalacao concluida (ou quase).
echo  Teste rapido de GPU:
echo    venv3d\Scripts\python -c "import torch;print('CUDA ok?',torch.cuda.is_available(),torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
echo.
echo  Depois, gerar um 3D a partir de uma imagem:
echo    venv3d\Scripts\python src\gerar3d.py --input input\personagem.png --out input\personagem.glb
echo ============================================================

:fim
endlocal
pause
