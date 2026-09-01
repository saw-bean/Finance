# ALPHAFORGE: Autonomous Multi-Agent Quant Trading & Financial Intelligence Platform

A production-grade, institutional multi-agent quant system designed to uncover asymmetric alpha without expensive institutional data subscriptions ($20k+/month Bloomberg/FactSet). Built entirely on free public market feeds (SEC EDGAR, FINRA, USASpending, open financial statements) with real-time web dashboard and paper trading simulation.

---

## Key Features

1. **Autonomous Specialist Agent Swarm:**
   - **SEC EDGAR & Footnote Sniper Agent:** Real-time polling for Form 4 open-market cluster buys ($>\$50\text{k}$) by C-suite executives, 8-K material definitive agreements, and 13D/G activist stake accumulations.
   - **Forensic Quant & Quality Screener Agent:** Calculates Piotroski F-Score (0–9), Beneish M-Score (earnings manipulation detection), Altman Z-Score (bankruptcy distress), and Sloan Accrual anomalies.
   - **Gov & Defense Contract Catalyst Agent:** Scrapes USASpending.gov awards to catch federal contracts relative to market cap before mainstream financial press coverage.
   - **Flow, FINRA Short & Squeeze Tracker:** Ingests daily FINRA short sale volume feeds and monitors float turnover to pinpoint short squeeze setups.
   - **CIO & Devil's Advocate Risk Agent:** Multi-agent consensus engine, fractional Kelly position sizing, mark-to-market valuations, stop-loss and take-profit enforcement.

2. **Full-Featured Institutional Dark Web Dashboard:**
   - **Live Alpha Stream:** Real-time stream of detected catalysts with conviction ratings and metadata inspection.
   - **Agent War Room:** Live status cards for all 5 agents with heartbeats, signal counters, execution triggers, and real-time streaming terminal logs.
   - **Forensic Screener:** Interactive search bar calculating on-demand Piotroski, Beneish, Altman scores and instant order execution.
   - **Paper Portfolio & Execution Engine:** Realistic simulated broker with slippage modeling, mark-to-market equity curve, open positions management, and historical trade ledger.
   - **In-Dashboard Settings Manager:** Live configuration of SEC User-Agent, Alpaca Paper API keys, Gemini/Ollama LLM models, and Discord/Telegram alert webhooks without server restart.

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
.venv/bin/pytest -v backend/tests/
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
