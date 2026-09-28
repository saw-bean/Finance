import json
import asyncio
import datetime
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.config import settings
from backend.db.models import Base, AgentState, AccountBalance, CatalystPerformance

db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

connect_args = {}
if "sqlite" in db_url:
    connect_args = {"timeout": 60.0}

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    connect_args=connect_args
)

if "sqlite" in db_url:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

async def commit_with_retry(session: AsyncSession, max_retries: int = 5, base_delay: float = 0.1):
    """Commits a session with automatic retry backoff."""
    for attempt in range(max_retries):
        try:
            await session.commit()
            return
        except OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                await session.rollback()
                await asyncio.sleep(base_delay * (attempt + 1))
            else:
                raise

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session_factory() as session:
        res = await session.execute(select(AccountBalance))
        acc = res.scalars().first()
        if not acc:
            acc = AccountBalance(
                cash=settings.PAPER_INITIAL_CASH,
                initial_capital=settings.PAPER_INITIAL_CASH
            )
            session.add(acc)
            
        default_agents = [
            {
                "name": "sec_edgar_agent",
                "display_name": "SEC EDGAR Filings Agent",
                "description": "Parses live Form 4 XML for insider open-market purchases over $50k, 8-K items (1.01, 4.01, 4.02) and new Schedule 13D stakes.",
            },
            {
                "name": "forensic_quant_agent",
                "display_name": "Forensic Quant & Quality Screener",
                "description": "Computes Piotroski F-Score, 8-variable Beneish M-Score, Altman Z-Score and Sloan accruals from Yahoo Finance annual statements.",
            },
            {
                "name": "contract_catalyst_agent",
                "display_name": "Gov & Defense Contract Catalyst Agent",
                "description": "Polls USASpending.gov for new federal awards over $10M to a watchlist of listed contractors (awards from the last 7 days only).",
            },
            {
                "name": "flow_gamma_agent",
                "display_name": "Short Interest Squeeze Tracker",
                "description": "Flags watchlist stocks with short interest over 15% of float or days-to-cover above 4.5 (Yahoo Finance data).",
            },
            {
                "name": "cio_risk_agent",
                "display_name": "CIO & Devil's Advocate Risk Agent",
                "description": "During market hours: vetoes red-flagged tickers, sizes positions by confidence and catalyst record, runs stops and fills paper orders.",
            },
            {
                "name": "learning_agent",
                "display_name": "Autonomous Learning & Reflection Engine",
                "description": "Records every closed trade by catalyst and turns each catalyst's smoothed win rate into a 0.5x-1.5x sizing weight.",
            },
            {
                "name": "web_intel_agent",
                "display_name": "Headline Sentiment Check",
                "description": "Pulls Google News headlines for each new signal and nudges its confidence up or down on bullish/bearish keywords.",
            },
            {
                "name": "boss_agent",
                "display_name": "Fund Auditor",
                "description": "Reports account, win rate, catalyst record and agent errors from the database every minute. Changes nothing.",
            },
        ]
        known_names = {d["name"] for d in default_agents}

        # Remove status rows for agents that no longer exist (e.g. retired generated agents)
        stale = (await session.execute(select(AgentState).where(AgentState.name.not_in(known_names)))).scalars().all()
        for row in stale:
            await session.delete(row)

        for agent_def in default_agents:
            res = await session.execute(select(AgentState).where(AgentState.name == agent_def["name"]))
            existing = res.scalars().first()
            if existing:
                existing.display_name = agent_def["display_name"]
                existing.description = agent_def["description"]
            else:
                session.add(AgentState(
                    name=agent_def["name"],
                    display_name=agent_def["display_name"],
                    description=agent_def["description"],
                    status="IDLE",
                    signals_generated=0,
                    errors_count=0,
                    stats=json.dumps({})
                ))

        # Seed Catalyst Performance Tracking
        default_catalysts = [
            ("SEC_FORM4_CLUSTER_BUY", "SEC Form 4 Insider Buys"),
            ("ACTIVIST_STAKE_13D", "Schedule 13D Activist Stakes"),
            ("FORENSIC_HIGH_QUALITY", "Forensic Quality Screen (F>=7, Z>2.99, M<-1.78)"),
            ("GOV_CONTRACT_AWARD", "Federal & Defense Contract Wins"),
            ("SHORT_SQUEEZE_SETUP", "Short Interest Squeeze Setups"),
            ("ACCOUNTING_RED_FLAG", "Accounting Red Flags / Shorts"),
            ("MANUAL_EXECUTION", "Manual Execution / Discretionary")
        ]
        
        for cat_type, d_name in default_catalysts:
            c_res = await session.execute(select(CatalystPerformance).where(CatalystPerformance.catalyst_type == cat_type))
            if not c_res.scalars().first():
                perf = CatalystPerformance(
                    catalyst_type=cat_type,
                    display_name=d_name,
                    total_trades=0,
                    wins=0,
                    losses=0,
                    win_rate=0.50,
                    total_pnl=0.0,
                    avg_return_pct=0.0,
                    calibrated_weight=1.0,
                    last_updated=datetime.datetime.now(datetime.UTC)
                )
                session.add(perf)

        await commit_with_retry(session)
