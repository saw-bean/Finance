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
    
    # Webhook Alerts & Telegram Push (Embedded Cloud Defaults)
    DISCORD_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = "8705428209:AAGs4TszbtcNNXfeYOgYkGiLVbm-DNE8ljw"
    TELEGRAM_CHAT_ID: Optional[str] = "8572984163"
    
    # Risk & Portfolio Parameters
    PAPER_INITIAL_CASH: float = 100.0
    MAX_POSITION_SIZE_PCT: float = 0.10
    DEFAULT_STOP_LOSS_PCT: float = 0.05
    DEFAULT_TAKE_PROFIT_PCT: float = 0.15
    MAX_DAILY_DRAWDOWN_PCT: float = 0.04
    SLIPPAGE_BPS: float = 5.0
    
    # Polling intervals (seconds)
    POLLING_INTERVAL_SEC_EDGAR: int = 60
    POLLING_INTERVAL_CONTRACTS: int = 300
    POLLING_INTERVAL_FINRA: int = 3600
    POLLING_INTERVAL_QUANT: int = 600

settings = Settings()
