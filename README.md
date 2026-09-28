# ALPHAFORGE: Autonomous Multi-Agent Quant Trading & Financial Intelligence Platform

A multi-agent paper-trading and research system built on free public data (SEC EDGAR, USASpending.gov, Yahoo Finance, Google News), with a web dashboard and optional Telegram alerts. Paper trading only: no real money is traded unless you connect an Alpaca account.

---

## Key Features

Paper-trading research platform built on free public data. Every signal comes from a real filing or data point; if data is missing the agent skips it rather than filling in a default.

1. **Agents:**
   - **SEC EDGAR Filings Agent:** Parses Form 4 XML for open-market purchases (code P) of $50k+ by officers/directors, 8-K Items 1.01 / 4.01 / 4.02, and new Schedule 13D stakes. Tickers come from SEC's CIK map.
   - **Forensic Quant Screener:** Piotroski F-Score (9 tests), 8-variable Beneish M-Score, Altman Z-Score and Sloan accruals from Yahoo Finance annual statements. Missing inputs give `None`, never a guess.
   - **Gov Contract Agent:** New USASpending.gov awards (last 7 days) to a contractor watchlist, only when the award is at least 0.5% of the company's market cap.
   - **Short Interest Squeeze Tracker:** Short % of float and days-to-cover from Yahoo Finance.
   - **Headline Sentiment Check:** Google News headlines per signal; nudges confidence on bullish/bearish keywords.
   - **CIO Risk Agent:** Fills paper orders only during regular NYSE hours; vetoes red-flagged tickers; expires signals older than 3 days; stop-loss / take-profit / trailing stops.
   - **Learning Agent:** Records each closed trade by catalyst and turns each catalyst's record into a 0.5x–1.5x sizing weight.
   - **Fund Auditor:** Read-only report of equity, win rate, catalyst record and agent errors.

2. **Web Dashboard** (login with `API_TOKEN`): live signals, agent status and logs, forensic screener, paper portfolio, settings.

3. **Telegram bot** (optional): trade alerts, morning/closing briefings, and simple commands (`/status`, `/portfolio`, `/boss`, `scan NVDA`).

---

## Quick Start Guide

### 1. Start the Platform
To launch the backend agent swarm and the web dashboard:
```bash
./start.sh
# or
python3 run.py
```

### 2. Access the Dashboard
Open your browser and navigate to:
```
http://localhost:8000
```

---

## Running 24/7 on Windows (`service.ps1`)

From an **Administrator** PowerShell in the repo folder:
```powershell
powershell -ExecutionPolicy Bypass -File .\service.ps1 -InstallTask   # start at boot, no login needed, sleep disabled on AC
powershell -ExecutionPolicy Bypass -File .\service.ps1 -StartTask
powershell -ExecutionPolicy Bypass -File .\service.ps1 -Status
```
Also `-Restart`, `-Update` (git pull + pip install + restart), `-StopTask`, `-UninstallTask`. Logs go to `data\supervisor.log` and `data\engine_*.log`.

## Dashboard login

`run.py` writes a random `API_TOKEN` to `.env` on first start and prints it. Open the dashboard and paste it, or visit `/login?token=<API_TOKEN>` once to set the cookie. Scripts can send it as `X-API-Key` or `Authorization: Bearer`.

---

## Configuration (`.env`)

All configurations are optional and come with sensible defaults. You can edit `.env` or use the Settings Modal in the top-right of the dashboard:

```env
# Required for SEC EDGAR (100% Free - Standard Format: SampleApp user@domain.com)
SEC_USER_AGENT=AlphaForgeTrader research@alphaforge.local

# Optional Alpaca Paper Trading (Free at https://app.alpaca.markets)
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_PAPER=true

# Optional LLM Intelligence (Local Ollama or Gemini)
GEMINI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:latest

# Optional Mobile Notifications (Discord or Telegram)
DISCORD_WEBHOOK_URL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Risk Management
PAPER_INITIAL_CASH=100000.0
MAX_POSITION_SIZE_PCT=0.10
DEFAULT_STOP_LOSS_PCT=0.05
DEFAULT_TAKE_PROFIT_PCT=0.15
```

---

## Automated Test Suite

Run the full pytest suite:
```bash
.venv/bin/pytest -v
```

---

## Project Structure

```
├── .env.example            # Environment template
├── README.md               # Documentation
├── requirements.txt        # Python dependencies
├── run.py                  # Production entry point
├── start.sh                # Shell launcher
├── backend/
│   ├── main.py             # FastAPI server with WebSocket hub & static mounting
│   ├── config.py           # Settings loader & validator
│   ├── agents/             # Autonomous agent swarm
│   │   ├── base.py
│   │   ├── sec_edgar.py
│   │   ├── forensic_quant.py
│   │   ├── contract_catalyst.py
│   │   ├── flow_gamma.py
│   │   └── cio_risk.py
│   ├── execution/          # Paper broker & Alpaca bridge
│   │   ├── paper_engine.py
│   │   └── alpaca_client.py
│   ├── db/                 # SQLite WAL engine & models
│   │   ├── models.py
│   │   └── session.py
│   ├── api/                # REST routes & WebSockets
│   │   ├── routes.py
│   │   └── websocket.py
│   ├── tests/              # Pytest unit & integration tests
│   └── static/             # Compiled production UI bundle
└── frontend/               # React + Vite + Tailwind source
```
