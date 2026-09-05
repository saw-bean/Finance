#!/bin/bash
set -e

echo "===================================================="
echo "   🚀 AlphaForge 24/7 Multi-Agent Quant Setup"
echo "===================================================="

# Detect OS
OS="$(uname -s)"
echo "[1/4] Operating System: $OS"

# Check Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 not found. Please install Python 3.10+."
    exit 1
fi

# Set up virtual environment
echo "[2/4] Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Ensure data directory exists
mkdir -p data

# Check Node / npm for frontend if needed
if command -v npm &> /dev/null; then
    if [ ! -d "backend/static/assets" ]; then
        echo "[3/4] Building production web dashboard..."
        cd frontend && npm install && npm run build && cd ..
    else
        echo "[3/4] Production web dashboard already built."
    fi
else
    echo "[3/4] npm not found, using pre-built static bundle in backend/static."
fi

echo "===================================================="
echo "   🟢 Starting AlphaForge Swarm 24/7 Daemon..."
echo "===================================================="
echo "• Web Dashboard: http://localhost:8000 (and http://$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}'):8000)"
echo "• Telegram Alerts: Active & Connected"
echo "• Stop with CTRL+C (or run with nohup to keep running in background)"
echo "===================================================="

# Start server
exec python3 run.py
