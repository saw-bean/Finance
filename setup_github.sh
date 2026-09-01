#!/bin/bash
# ==============================================================================
# ALPHAFORGE GITHUB SETUP SCRIPT
# Prepares and commits the codebase to GitHub
# ==============================================================================

set -e

REPO_DIR="/Volumes/CHAOS/Finance"
cd "$REPO_DIR"

echo "======================================================================"
echo "    INITIALIZING GITHUB REPOSITORY FOR ALPHAFORGE"
echo "======================================================================"

if [ ! -d ".git" ]; then
    echo "[*] Initializing Git repository..."
    git init
    git branch -M main
fi

echo "[*] Staging files (excluding secrets and virtual environments)..."
git add .

echo "[*] Creating initial commit..."
git commit -m "feat: initial release of AlphaForge autonomous multi-agent quant engine" || echo "[i] No new changes to commit."

echo "----------------------------------------------------------------------"
echo "[SUCCESS] Local Git repository is ready!"
echo ""
echo "To push to your GitHub account, run:"
echo "  1. Create a new empty repository on https://github.com/new"
echo "  2. Run the following commands:"
echo ""
echo "     git remote add origin https://github.com/YOUR_USERNAME/alphaforge.git"
echo "     git push -u origin main"
echo ""
echo "======================================================================"
