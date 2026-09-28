#!/usr/bin/env python3
import os
import sys
import subprocess
import uvicorn
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

def print_banner():
    banner = r"""
======================================================================
     ___    __    ____  __  _____    ______ ____  ____   ______ ______
    /   |  / /   / __ \/ / / /   |  / ____// __ \/ __ \ / ____// ____/
   / /| | / /   / /_/ / /_/ / /| | / /_   / / / / /_/ // / __ / __/   
  / ___ |/ /___/ ____/ __  / ___ |/ __/  / /_/ / _, _// /_/ // /___   
 /_/  |_/_____/_/   /_/ /_/_/  |_/_/     \____/_/ |_| \____//_____/   
                                                                       
        QUANT MULTI-AGENT TRADING & INTEL ENGINE (PRODUCTION)
======================================================================
"""
    print(banner)

def ensure_api_token(env_file: Path):
    """Generates an API_TOKEN in .env on first run so the dashboard is never left open."""
    import secrets
    text = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    for line in text.splitlines():
        if line.startswith("API_TOKEN=") and line.split("=", 1)[1].strip():
            return
    token = secrets.token_urlsafe(24)
    lines = [l for l in text.splitlines() if not l.startswith("API_TOKEN=")]
    lines.append(f"API_TOKEN={token}")
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[INFO] Generated API_TOKEN in .env. Dashboard login token: {token}")

def verify_environment():
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        example_file = BASE_DIR / ".env.example"
        if example_file.exists():
            import shutil
            shutil.copy(str(example_file), str(env_file))
            print("[INFO] Created .env from .env.example")
            
    ensure_api_token(env_file)

    static_index = BASE_DIR / "backend" / "static" / "index.html"
    if not static_index.exists():
        print("[INFO] Building frontend bundle...")
        try:
            subprocess.run(["npm", "run", "build"], cwd=str(BASE_DIR / "frontend"), check=True)
        except Exception as e:
            print(f"[WARN] Failed to build frontend automatically: {e}")

def main():
    print_banner()
    verify_environment()
    
    from backend.config import settings
    print(f"[*] Starting AlphaForge Server on http://{settings.HOST}:{settings.PORT}")
    print(f"[*] Environment: {settings.ENVIRONMENT}")
    print(f"[*] SEC EDGAR Header: {settings.SEC_USER_AGENT}")
    print(f"[*] Alpaca Paper Broker: {'Configured' if settings.ALPACA_API_KEY else 'Disabled (Local Engine Active)'}")
    print(f"[*] Press CTRL+C to stop.\n")
    
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
