import json
import asyncio
import datetime
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.config import settings
from backend.db.models import Base, AgentState, AccountBalance, CatalystPerformance

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"timeout": 60.0}
)

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
    """Commits a session with automatic retry backoff if SQLite is momentarily busy."""
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
                "display_name": "SEC EDGAR & Footnote Sniper",
                "description": "Real-time poller for SEC 8-K material events, Form 4 insider cluster purchases, and 13D/G activist stakes.",
            },
            {
                "name": "forensic_quant_agent",
                "display_name": "Forensic Quant & Quality Screener",
                "description": "Calculates Piotroski F-Score, Beneish M-Score, and Altman Z-Score for sub-$2B equities to flag manipulation or deep value.",
            },
            {
                "name": "contract_catalyst_agent",
                "display_name": "Gov & Defense Contract Catalyst Agent",
                "description": "Monitors USASpending.gov awards to uncover small-cap defense and tech contract wins before market pricing.",
            },
            {
                "name": "flow_gamma_agent",
                "display_name": "Flow, FINRA Short & Squeeze Tracker",
                "description": "Monitors FINRA daily short volumes and CBOE put/call flow to pinpoint asymmetric short squeeze setups.",
            },
            {
                "name": "cio_risk_agent",
                "display_name": "CIO & Devil's Advocate Risk Agent",
                "description": "Cross-validates multi-agent signals, calculates fractional Kelly sizing, runs stop-loss monitoring, and executes paper orders.",
            },
            {
                "name": "learning_agent",
                "display_name": "Autonomous Learning & Reflection Engine",
                "description": "Analyzes closed trades, calculates Bayesian win rates per catalyst, and dynamically recalibrates AI conviction weights.",
            }
        ]
        
        for agent_def in default_agents:
            res = await session.execute(select(AgentState).where(AgentState.name == agent_def["name"]))
            existing = res.scalars().first()
            if not existing:
                agent_state = AgentState(
                    name=agent_def["name"],
                    display_name=agent_def["display_name"],
                    description=agent_def["description"],
                    status="IDLE",
                    signals_generated=0,
                    errors_count=0,
                    stats=json.dumps({"uptime": 0, "last_action": "Initialized"})
                )
                session.add(agent_state)
                
        # Seed Catalyst Performance Tracking
        default_catalysts = [
            ("SEC_FORM4_CLUSTER_BUY", "SEC Form 4 Insider Buys"),
            ("FORENSIC_HIGH_QUALITY", "Forensic Quality Screener (Piotroski 8-9)"),
            ("GOV_CONTRACT_AWARD", "Federal & Defense Contract Wins"),
            ("SHORT_SQUEEZE_SETUP", "FINRA Short Squeeze Setups"),
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
                    win_rate=0.50, # Initial prior
                    total_pnl=0.0,
                    avg_return_pct=0.0,
                    calibrated_weight=1.0,
                    last_updated=datetime.datetime.now(datetime.UTC)
                )
                session.add(perf)

        await commit_with_retry(session)
