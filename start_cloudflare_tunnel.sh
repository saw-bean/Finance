#!/bin/bash
# ==============================================================================
# ALPHAFORGE CLOUDFLARE 24/7 TUNNEL LAUNCHER
# Exposes AlphaForge locally/server to a secure public Cloudflare URL (24/7)
# ==============================================================================

set -e

PORT=${1:-8000}

echo "======================================================================"
echo "    ALPHAFORGE & CLOUDFLARE ZERO TRUST 24/7 TUNNEL"
echo "======================================================================"

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "[!] cloudflared is not installed."
    echo "[*] Attempting to install cloudflared via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install cloudflared
    else
        echo "[ERROR] Homebrew not found. Please install cloudflared manually from:"
        echo "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
        exit 1
    fi
fi

echo "[*] Checking if AlphaForge backend is running on port $PORT..."
if ! curl -s http://localhost:$PORT/api/status > /dev/null; then
    echo "[!] AlphaForge is not responding on port $PORT."
    echo "[*] Starting AlphaForge server..."
    ./start.sh &
    sleep 3
fi

echo "[*] Starting Cloudflare Quick Tunnel to http://localhost:$PORT..."
echo "[*] Your public, encrypted HTTPS URL will appear below:"
echo "----------------------------------------------------------------------"

cloudflared tunnel --url http://localhost:$PORT
