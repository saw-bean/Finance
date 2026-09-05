@echo off
echo ====================================================
echo    AlphaForge 24/7 Multi-Agent Quant Engine
echo ====================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ and check Add to PATH.
    pause
    exit /b
)

if not exist ".venv" (
    echo [1/3] Creating Python virtual environment...
    python -m venv .venv
)

echo [2/3] Installing requirements...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist "data" mkdir data

echo ====================================================
echo    AlphaForge 24/7 Swarm Running!
echo    Dashboard: http://localhost:8000
echo    Tailscale: http://100.81.54.5:8000
echo ====================================================

python run.py
pause
