import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Signal(Base):
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), index=True)
    ticker = Column(String(16), index=True)
    agent_name = Column(String(64), index=True)
    catalyst_type = Column(String(64), index=True)
    action = Column(String(16), default="BUY")
    confidence = Column(Float, default=0.5)
    title = Column(String(256))
    summary = Column(Text)
    raw_metadata = Column(Text, default="{}")
    processed = Column(Boolean, default=False)

class Position(Base):
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(16), unique=True, index=True)
    qty = Column(Float, default=0.0)
    avg_entry_price = Column(Float, default=0.0)
    current_price = Column(Float, default=0.0)
    market_value = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    catalyst = Column(String(128), default="")
    entry_time = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))
    # qty < 0 means a short position
    side = Column(String(8), default="LONG")
    agent_name = Column(String(64), default="")
    sector = Column(String(64), nullable=True)
    borrow_rate = Column(Float, default=0.0)        # annual rate charged on short market value
    extreme_price = Column(Float, nullable=True)    # best price since entry (high for longs, low for shorts), for trailing stops
    exit_by = Column(DateTime, nullable=True)       # time stop: the signal's holding horizon

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), index=True)
    symbol = Column(String(16), index=True)
    side = Column(String(8)) # BUY, SELL
    qty = Column(Float)
    price = Column(Float)
    slippage = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    total_cost = Column(Float)
    realized_pnl = Column(Float, default=0.0)
    reason = Column(Text)
    broker = Column(String(32), default="SIMULATED_PAPER")
    # side: BUY, SELL (close long), SHORT, COVER (close short)
    catalyst = Column(String(128), default="")
    agent_name = Column(String(64), default="")
    fees = Column(Float, default=0.0)          # SEC fee + FINRA TAF (commission is recorded separately)
    mid_price = Column(Float, nullable=True)   # quote midpoint at fill; price - mid = spread paid
    quote_source = Column(String(16), default="")  # LIVE_QUOTE or MODELED_SPREAD

class AgentState(Base):
    __tablename__ = "agent_states"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, index=True)
    display_name = Column(String(128))
    description = Column(String(256))
    status = Column(String(32), default="IDLE") # RUNNING, IDLE, POLLING, ERROR, DISABLED
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    signals_generated = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    stats = Column(Text, default="{}")

class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), index=True)
    agent_name = Column(String(64), index=True)
    level = Column(String(16), default="INFO") # INFO, WARNING, ERROR, ACTION, ALPHA
    message = Column(Text)
    ticker = Column(String(16), nullable=True, index=True)

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), index=True)
    total_equity = Column(Float)
    cash = Column(Float)
    positions_value = Column(Float)
    daily_pnl = Column(Float, default=0.0)
    daily_pnl_pct = Column(Float, default=0.0)
    long_value = Column(Float, default=0.0)
    short_value = Column(Float, default=0.0)   # absolute value of short positions

class CashLedger(Base):
    """Cash movements that are not trades (short borrow fees, etc.)."""
    __tablename__ = "cash_ledger"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), index=True)
    kind = Column(String(32), index=True)  # BORROW_FEE
    symbol = Column(String(16), nullable=True)
    amount = Column(Float)                 # negative = cash out
    note = Column(String(256), default="")

class AccountBalance(Base):
    __tablename__ = "account_balance"
    
    id = Column(Integer, primary_key=True, index=True)
    cash = Column(Float, default=100.0)
    initial_capital = Column(Float, default=100.0)
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

class TradeReflection(Base):
    __tablename__ = "trade_reflections"
    
    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(Integer, nullable=True, index=True)
    symbol = Column(String(16), index=True)
    side = Column(String(8))
    catalyst = Column(String(128))
    entry_price = Column(Float)
    exit_price = Column(Float)
    realized_pnl = Column(Float)
    pnl_pct = Column(Float)
    outcome = Column(String(16)) # WIN, LOSS, BREAKEVEN
    reflection_summary = Column(Text)
    lessons_learned = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), index=True)

class CatalystPerformance(Base):
    __tablename__ = "catalyst_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    catalyst_type = Column(String(128), unique=True, index=True)
    display_name = Column(String(128))
    total_trades = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    win_rate = Column(Float, default=0.5) # Default 50% prior
    total_pnl = Column(Float, default=0.0)
    avg_return_pct = Column(Float, default=0.0)
    calibrated_weight = Column(Float, default=1.0) # Multiplier: 0.5x to 1.5x
    last_updated = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

class BossDirective(Base):
    __tablename__ = "boss_directives"
    
    id = Column(Integer, primary_key=True, index=True)
    directive_key = Column(String(64), unique=True, index=True)
    category = Column(String(32)) # RISK_TUNING, STRATEGY_WEIGHT, AGENT_CONTROL, REGIME_OVERRIDE
    value = Column(Text) # JSON serialized parameters/values
    description = Column(String(256))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))

class SystemEvolution(Base):
    __tablename__ = "system_evolutions"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), index=True)
    action_type = Column(String(64), index=True) # STRATEGY_SYNTHESIS, AGENT_SPAWNED, CODE_DEPLOYED, PARAMETER_TUNING, ARCHITECTURAL_AUDIT
    title = Column(String(256))
    description = Column(Text)
    code_path = Column(String(256), nullable=True)
    code_content = Column(Text, nullable=True)
    ast_verified = Column(Boolean, default=True)
    sandbox_passed = Column(Boolean, default=True)
    target_agent = Column(String(64), nullable=True)
    impact_metrics = Column(Text, default="{}") # JSON string of expected or actual metrics
    status = Column(String(32), default="ACTIVE") # ACTIVE, VERIFIED, PAUSED, DEPRECATED

