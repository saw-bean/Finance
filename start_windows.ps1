Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "   🚀 AlphaForge 24/7 Multi-Agent Quant Engine" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python is not found! Please install Python 3.10+ from python.org." -ForegroundColor Red
    Pause
    Exit
}

# Create virtual environment if missing
if (-not (Test-Path ".venv")) {
    Write-Host "[1/3] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "[2/3] Installing dependencies..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# Create data directory
if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}

Write-Host "====================================================" -ForegroundColor Green
Write-Host "   🟢 AlphaForge Swarm 24/7 is Starting..." -ForegroundColor Green
Write-Host "• Local Dashboard:     http://localhost:8000" -ForegroundColor White
Write-Host "• Tailscale Network:   http://100.81.54.5:8000" -ForegroundColor White
Write-Host "• Telegram Alerts:     Active & Connected" -ForegroundColor White
Write-Host "• Persistent Storage:  data\alphaforge.db (Never resets!)" -ForegroundColor White
Write-Host "====================================================" -ForegroundColor Green

python run.py
