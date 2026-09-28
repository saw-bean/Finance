import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENVIRONMENT: str = "production"

    # Required to use the dashboard/API when set. run.py generates one on first start.
    API_TOKEN: Optional[str] = None
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/alphaforge.db"
    LOG_FILE_PATH: str = f"{BASE_DIR}/data/system_audit.log"
    
    # SEC EDGAR
    SEC_USER_AGENT: str = "AlphaForgeTrader research@alphaforge.local"
    
    # Alpaca Paper Broker
    ALPACA_API_KEY: Optional[str] = None
    ALPACA_SECRET_KEY: Optional[str] = None
    ALPACA_PAPER: bool = True
    ALPACA_BASE_URL: str = "https://paper-api.alpaca.markets"
    
    # LLM Services
    GEMINI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "deepseek-r1:latest"
    
    # Webhook Alerts & Telegram Push (set in .env, never commit secrets)
    DISCORD_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    
    # Risk & Portfolio Parameters
    PAPER_INITIAL_CASH: float = 100.0
    MAX_POSITION_SIZE_PCT: float = 0.10
    DEFAULT_STOP_LOSS_PCT: float = 0.05
    DEFAULT_TAKE_PROFIT_PCT: float = 0.15
    MAX_DAILY_DRAWDOWN_PCT: float = 0.04    # no new entries for the rest of the day past this loss
    # Long/short portfolio limits (fractions of equity)
    ALLOW_SHORTS: bool = True
    MAX_GROSS_EXPOSURE: float = 1.5
    MAX_NET_EXPOSURE: float = 1.0
    MIN_NET_EXPOSURE: float = -0.3
    MAX_SECTOR_PCT: float = 0.35
    MIN_LONG_PRICE: float = 2.0
    MIN_SHORT_PRICE: float = 5.0            # brokers don't lend (marginable) stocks under $5
    MIN_CONFIDENCE: float = 0.78
    SLIPPAGE_BPS: float = 5.0
    
    # Polling intervals (seconds)
    POLLING_INTERVAL_SEC_EDGAR: int = 60
    POLLING_INTERVAL_CONTRACTS: int = 300
    POLLING_INTERVAL_FINRA: int = 3600
    POLLING_INTERVAL_QUANT: int = 600

settings = Settings()
