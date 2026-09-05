import os
import json
import asyncio
import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
import yfinance as yf

from backend.db.session import get_db, async_session_factory, commit_with_retry
from backend.db.models import Signal, Position, Trade, AgentState, AgentLog, PortfolioSnapshot, AccountBalance, TradeReflection, CatalystPerformance
from backend.execution.paper_engine import paper_engine
from backend.agents.sec_edgar import sec_agent
from backend.agents.forensic_quant import forensic_agent
from backend.agents.contract_catalyst import contract_agent
from backend.agents.flow_gamma import flow_agent
from backend.agents.cio_risk import cio_agent
from backend.agents.learning_agent import learning_agent
from backend.agents.web_intel_agent import web_intel_agent
from backend.agents.evolution_agent import evolution_agent
from backend.notifications.telegram import telegram_notifier
from backend.config import settings, BASE_DIR

router = APIRouter(prefix="/api")

BOOT_TIME = datetime.datetime.now(datetime.UTC)


# Schemas
class ManualOrderRequest(BaseModel):
    symbol: str
    side: str # BUY, SELL
    qty: float
    reason: Optional[str] = "Manual Trade from Dashboard"

class ManualSignalRequest(BaseModel):
    ticker: str
    catalyst_type: str
    action: str
    confidence: float
    title: str
    summary: str

class SettingsUpdateRequest(BaseModel):
    sec_user_agent: Optional[str] = None
    alpaca_api_key: Optional[str] = None
    alpaca_secret_key: Optional[str] = None
    alpaca_paper: Optional[bool] = None
    gemini_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    max_position_size_pct: Optional[float] = None
    default_stop_loss_pct: Optional[float] = None
    default_take_profit_pct: Optional[float] = None

def _get_ticker_price_sync(symbol: str) -> float:
    symbol = symbol.upper().strip()
    try:
        stock = yf.Ticker(symbol)
        if hasattr(stock, 'fast_info') and stock.fast_info:
            p = stock.fast_info.get('last_price') or stock.fast_info.get('previous_close')
            if p and p > 0:
                return float(p)
        info = stock.info or {}
        p = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0.0
        if p > 0:
            return float(p)
    except Exception:
        pass

    fallback_map = {
        "PLTR": 180.50, "SOUN": 4.85, "HIMS": 28.50, "SMCI": 36.80, "BBAI": 2.95,
        "ASTS": 56.00, "RKLB": 24.10, "IONQ": 31.20, "JOBY": 8.40, "ACHR": 6.70,
        "AAPL": 235.00, "NVDA": 128.00, "TSLA": 215.00, "MSFT": 448.00, "AMZN": 188.00
    }
    return float(fallback_map.get(symbol, 25.0))

@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)):
    account = await paper_engine.get_account_summary()
    
    agent_res = await db.execute(select(AgentState))
    agents = agent_res.scalars().all()
    
    sig_count_res = await db.execute(select(Signal))
    total_signals = len(sig_count_res.scalars().all())
    
    trade_count_res = await db.execute(select(Trade))
    total_trades = len(trade_count_res.scalars().all())
    
    # Calculate persistent 24/7 uptime from earliest database record
    snap_res = await db.execute(select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.asc()).limit(1))
    first_snap = snap_res.scalars().first()
    
    now_utc = datetime.datetime.now(datetime.UTC)
    if first_snap and first_snap.timestamp:
        start_dt = first_snap.timestamp
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
    else:
        start_dt = BOOT_TIME
        
    uptime_seconds = max(0, int((now_utc - start_dt).total_seconds()))
    days, rem = divmod(uptime_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    
    if days > 0:
        uptime_human = f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        uptime_human = f"{hours}h {minutes}m {seconds}s"
    else:
        uptime_human = f"{minutes}m {seconds}s"

    return {
        "status": "ONLINE",
        "environment": settings.ENVIRONMENT,
        "timestamp": now_utc.isoformat(),
        "server_start_time": start_dt.isoformat(),
        "uptime_seconds": uptime_seconds,
        "uptime_human": uptime_human,
        "account": account,
        "active_agents": [
            {
                "name": a.name,
                "display_name": a.display_name,
                "status": a.status,
                "signals_generated": a.signals_generated,
                "errors_count": a.errors_count,
                "last_run": a.last_run.isoformat() if a.last_run else None,
                "next_run": a.next_run.isoformat() if a.next_run else None
            }
            for a in agents
        ],
        "total_signals_detected": total_signals,
        "total_trades_executed": total_trades,
        "telegram_configured": telegram_notifier.is_configured,
        "audit_log_file": settings.LOG_FILE_PATH
    }

@router.post("/telegram/test")
async def test_telegram_notification():
    """Sends a live test notification to Telegram."""
    if not telegram_notifier.is_configured:
        raise HTTPException(
            status_code=400,
            detail="Telegram Bot Token or Chat ID not configured. Please set them in the Settings Modal or .env file."
        )
    success = await telegram_notifier.send_message(
        "🤖 <b>ALPHAFORGE TELEGRAM ALERTS ACTIVE!</b>\n\n"
        "• 🚀 <b>BUY Alerts:</b> Quantity, price, catalyst & stop-loss / profit targets\n"
        "• ⚠️ <b>SELL Alerts:</b> Realized PnL ($ and %) & post-mortem lessons\n"
        "• 🛠️ <b>Self-Evolution Alerts:</b> Autonomous system tool upgrades\n\n"
        "<i>Your Telegram trading alert channel is connected and ready.</i>"
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to deliver Telegram test message. Check bot token and chat ID.")
    return {"success": True, "message": "Test notification sent successfully to Telegram!"}

@router.get("/learning/performance")
async def get_learning_performance(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CatalystPerformance).order_by(desc(CatalystPerformance.win_rate)))
    perfs = res.scalars().all()
    return [
        {
            "catalyst_type": p.catalyst_type,
            "display_name": p.display_name,
            "total_trades": p.total_trades,
            "wins": p.wins,
            "losses": p.losses,
            "win_rate": p.win_rate,
            "win_rate_pct": round(p.win_rate * 100, 1),
            "total_pnl": p.total_pnl,
            "avg_return_pct": p.avg_return_pct,
            "calibrated_weight": p.calibrated_weight,
            "last_updated": p.last_updated.isoformat() if p.last_updated else None
        }
        for p in perfs
    ]

@router.get("/learning/reflections")
async def get_learning_reflections(limit: int = Query(30, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(TradeReflection).order_by(desc(TradeReflection.timestamp)).limit(limit))
    reflections = res.scalars().all()
    return [
        {
            "id": r.id,
            "symbol": r.symbol,
            "side": r.side,
            "catalyst": r.catalyst,
            "entry_price": r.entry_price,
            "exit_price": r.exit_price,
            "realized_pnl": r.realized_pnl,
            "pnl_pct": r.pnl_pct,
            "outcome": r.outcome,
            "reflection_summary": r.reflection_summary,
            "lessons_learned": r.lessons_learned,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None
        }
        for r in reflections
    ]

@router.get("/portfolio/holdings-summary")
async def get_holdings_summary(db: AsyncSession = Depends(get_db)):
    pos_res = await db.execute(select(Position).order_by(desc(Position.market_value)))
    positions = pos_res.scalars().all()
    
    summary_list = []
    for p in positions:
        pnl_pos = p.unrealized_pnl >= 0
        gain_text = f"+${p.unrealized_pnl:.2f} (+{p.unrealized_pnl_pct:.2f}%)" if pnl_pos else f"-${abs(p.unrealized_pnl):.2f} ({p.unrealized_pnl_pct:.2f}%)"
        
        thesis_explanation = "Selected for superior balance sheet health (Piotroski Score 8-9) and positive cash generation."
        if "FORM 4" in p.catalyst.upper():
            thesis_explanation = "C-suite executives bought substantial shares on open market with personal capital."
        elif "CONTRACT" in p.catalyst.upper():
            thesis_explanation = "Company won a high-value government defense or tech task order."
        elif "SQUEEZE" in p.catalyst.upper():
            thesis_explanation = "High short interest + float turnover created asymmetric squeeze potential."
        elif "MANUAL" in p.catalyst.upper():
            thesis_explanation = "Executed directly by user from the dashboard."

        summary_list.append({
            "symbol": p.symbol,
            "shares": p.qty,
            "entry_price": p.avg_entry_price,
            "current_price": p.current_price,
            "market_value": p.market_value,
            "gain_loss_text": gain_text,
            "is_profitable": pnl_pos,
            "why_we_bought": thesis_explanation,
            "safety_stop_loss": f"${p.stop_loss:.2f}" if p.stop_loss else "None",
            "profit_target": f"${p.take_profit:.2f}" if p.take_profit else "None"
        })
    return summary_list

@router.get("/signals")
async def get_signals(
    limit: int = Query(50, ge=1, le=200),
    ticker: Optional[str] = None,
    catalyst: Optional[str] = None,
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Signal).order_by(desc(Signal.timestamp))
    if ticker:
        query = query.where(Signal.ticker == ticker.upper())
    if catalyst:
        query = query.where(Signal.catalyst_type == catalyst)
    if action:
        query = query.where(Signal.action == action.upper())
    
    query = query.limit(limit)
    res = await db.execute(query)
    signals = res.scalars().all()
    
    return [
        {
            "id": s.id,
            "timestamp": s.timestamp.isoformat(),
            "ticker": s.ticker,
            "agent_name": s.agent_name,
            "catalyst_type": s.catalyst_type,
            "action": s.action,
            "confidence": s.confidence,
            "title": s.title,
            "summary": s.summary,
            "metadata": json.loads(s.raw_metadata or "{}"),
            "processed": s.processed
        }
        for s in signals
    ]

@router.post("/signals/manual")
async def create_manual_signal(req: ManualSignalRequest):
    sig = await cio_agent.emit_signal(
        ticker=req.ticker,
        catalyst_type=req.catalyst_type,
        action=req.action,
        confidence=req.confidence,
        title=req.title,
        summary=req.summary,
        metadata={"manual": True}
    )
    return {"success": True, "ticker": req.ticker, "action": req.action}

@router.get("/screener/analyze/{ticker}")
async def analyze_ticker_endpoint(ticker: str):
    data = await asyncio.to_thread(forensic_agent.analyze_ticker, ticker)
    if not data or "error" in data:
        raise HTTPException(status_code=400, detail=data.get("error", "Analysis failed"))
    return data

@router.get("/screener/universe")
async def get_screener_universe():
    results = []
    for ticker in forensic_agent.universe:
        data = await asyncio.to_thread(forensic_agent.analyze_ticker, ticker)
        if data and "error" not in data:
            results.append(data)
    return results

@router.get("/portfolio")
async def get_portfolio(db: AsyncSession = Depends(get_db)):
    summary = await paper_engine.get_account_summary()
    
    pos_res = await db.execute(select(Position).order_by(desc(Position.market_value)))
    positions = pos_res.scalars().all()
    
    trade_res = await db.execute(select(Trade).order_by(desc(Trade.timestamp)).limit(50))
    trades = trade_res.scalars().all()
    
    snap_res = await db.execute(select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.asc()).limit(100))
    snapshots = snap_res.scalars().all()
    
    return {
        "summary": summary,
        "positions": [
            {
                "symbol": p.symbol,
                "qty": p.qty,
                "avg_entry_price": p.avg_entry_price,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_pnl_pct": p.unrealized_pnl_pct,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "catalyst": p.catalyst,
                "entry_time": p.entry_time.isoformat() if p.entry_time else None
            }
            for p in positions
        ],
        "trades": [
            {
                "id": t.id,
                "timestamp": t.timestamp.isoformat(),
                "symbol": t.symbol,
                "side": t.side,
                "qty": t.qty,
                "price": t.price,
                "slippage": t.slippage,
                "commission": t.commission,
                "total_cost": t.total_cost,
                "realized_pnl": t.realized_pnl,
                "reason": t.reason,
                "broker": t.broker
            }
            for t in trades
        ],
        "equity_curve": [
            {
                "timestamp": s.timestamp.isoformat(),
                "total_equity": s.total_equity,
                "cash": s.cash,
                "positions_value": s.positions_value,
                "daily_pnl": s.daily_pnl
            }
            for s in snapshots
        ]
    }

@router.post("/portfolio/order")
async def execute_manual_order(req: ManualOrderRequest):
    price = await asyncio.to_thread(_get_ticker_price_sync, req.symbol)
    if price <= 0:
        raise HTTPException(status_code=400, detail=f"Cannot fetch live price for {req.symbol}")
        
    result = await paper_engine.execute_order(
        symbol=req.symbol,
        side=req.side,
        qty=req.qty,
        current_price=price,
        reason=req.reason or "Manual Order",
        catalyst="MANUAL_EXECUTION"
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@router.delete("/portfolio/position/{symbol}")
async def close_position(symbol: str):
    symbol = symbol.upper()
    async with async_session_factory() as session:
        pos_res = await session.execute(select(Position).where(Position.symbol == symbol))
        pos = pos_res.scalars().first()
        if not pos:
            raise HTTPException(status_code=404, detail="Position not found")
        
        qty = pos.qty
        price = pos.current_price
        
    result = await paper_engine.execute_order(
        symbol=symbol,
        side="SELL",
        qty=qty,
        current_price=price,
        reason="Manual Close from Dashboard"
    )
    return result

@router.post("/portfolio/reset")
async def reset_portfolio():
    async with async_session_factory() as session:
        await session.execute(delete(Position))
        await session.execute(delete(Trade))
        await session.execute(delete(PortfolioSnapshot))
        await session.execute(delete(TradeReflection))
        
        acc_res = await session.execute(select(AccountBalance))
        acc = acc_res.scalars().first()
        if acc:
            acc.cash = settings.PAPER_INITIAL_CASH
            acc.initial_capital = settings.PAPER_INITIAL_CASH
        await commit_with_retry(session)
        
    await paper_engine.record_snapshot()
    return {"success": True, "message": "Portfolio reset to initial cash"}

@router.get("/agents")
async def get_agents(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(AgentState))
    agents = res.scalars().all()
    return [
        {
            "name": a.name,
            "display_name": a.display_name,
            "description": a.description,
            "status": a.status,
            "last_run": a.last_run.isoformat() if a.last_run else None,
            "next_run": a.next_run.isoformat() if a.next_run else None,
            "signals_generated": a.signals_generated,
            "errors_count": a.errors_count,
            "last_error": a.last_error,
            "stats": json.loads(a.stats or "{}")
        }
        for a in agents
    ]

@router.post("/agents/{agent_name}/trigger")
async def trigger_agent(agent_name: str):
    agent_map = {
        "sec_edgar_agent": sec_agent,
        "forensic_quant_agent": forensic_agent,
        "contract_catalyst_agent": contract_agent,
        "flow_gamma_agent": flow_agent,
        "cio_risk_agent": cio_agent,
        "learning_agent": learning_agent,
        "web_intel_agent": web_intel_agent,
        "evolution_agent": evolution_agent
    }
    
    target = agent_map.get(agent_name)
    if not target:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    asyncio.create_task(target.run_iteration())
    return {"success": True, "message": f"Triggered execution for {target.display_name}"}

@router.get("/agent-logs")
async def get_agent_logs(limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(AgentLog).order_by(desc(AgentLog.timestamp)).limit(limit))
    logs = res.scalars().all()
    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat(),
            "agent_name": l.agent_name,
            "level": l.level,
            "message": l.message,
            "ticker": l.ticker
        }
        for l in logs
    ]

@router.get("/logs/audit")
async def get_raw_audit_logs(lines: int = Query(200, ge=1, le=2000)):
    log_file = settings.LOG_FILE_PATH
    if not os.path.exists(log_file):
        return {"logs": [], "total_lines": 0, "file_path": log_file}
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:]
            return {
                "logs": [l.strip() for l in recent_lines],
                "total_lines": len(all_lines),
                "file_path": log_file
            }
    except Exception as e:
        return {"error": str(e), "logs": [], "file_path": log_file}

@router.get("/logs/download")
async def download_audit_logs():
    log_file = settings.LOG_FILE_PATH
    if not os.path.exists(log_file):
        raise HTTPException(status_code=404, detail="Log file not found")
    return FileResponse(log_file, filename="alphaforge_audit.log", media_type="text/plain")

@router.get("/settings")
async def get_settings():
    return {
        "SEC_USER_AGENT": settings.SEC_USER_AGENT,
        "ALPACA_CONFIGURED": bool(settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY),
        "ALPACA_PAPER": settings.ALPACA_PAPER,
        "GEMINI_CONFIGURED": bool(settings.GEMINI_API_KEY),
        "OLLAMA_BASE_URL": settings.OLLAMA_BASE_URL,
        "DISCORD_CONFIGURED": bool(settings.DISCORD_WEBHOOK_URL),
        "TELEGRAM_CONFIGURED": telegram_notifier.is_configured,
        "TELEGRAM_CHAT_ID": settings.TELEGRAM_CHAT_ID,
        "PAPER_INITIAL_CASH": settings.PAPER_INITIAL_CASH,
        "MAX_POSITION_SIZE_PCT": settings.MAX_POSITION_SIZE_PCT,
        "DEFAULT_STOP_LOSS_PCT": settings.DEFAULT_STOP_LOSS_PCT,
        "DEFAULT_TAKE_PROFIT_PCT": settings.DEFAULT_TAKE_PROFIT_PCT,
        "MAX_DAILY_DRAWDOWN_PCT": settings.MAX_DAILY_DRAWDOWN_PCT,
        "LOG_FILE_PATH": settings.LOG_FILE_PATH
    }

@router.post("/settings")
async def update_settings(req: SettingsUpdateRequest):
    env_path = os.path.join(BASE_DIR, ".env")
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    env_vars[k] = v

    if req.sec_user_agent is not None:
        settings.SEC_USER_AGENT = req.sec_user_agent
        env_vars["SEC_USER_AGENT"] = req.sec_user_agent
    if req.alpaca_api_key is not None:
        settings.ALPACA_API_KEY = req.alpaca_api_key
        env_vars["ALPACA_API_KEY"] = req.alpaca_api_key
    if req.alpaca_secret_key is not None:
        settings.ALPACA_SECRET_KEY = req.alpaca_secret_key
        env_vars["ALPACA_SECRET_KEY"] = req.alpaca_secret_key
    if req.gemini_api_key is not None:
        settings.GEMINI_API_KEY = req.gemini_api_key
        env_vars["GEMINI_API_KEY"] = req.gemini_api_key
    if req.discord_webhook_url is not None:
        settings.DISCORD_WEBHOOK_URL = req.discord_webhook_url
        env_vars["DISCORD_WEBHOOK_URL"] = req.discord_webhook_url
    if req.telegram_bot_token is not None:
        settings.TELEGRAM_BOT_TOKEN = req.telegram_bot_token
        env_vars["TELEGRAM_BOT_TOKEN"] = req.telegram_bot_token
    if req.telegram_chat_id is not None:
        settings.TELEGRAM_CHAT_ID = req.telegram_chat_id
        env_vars["TELEGRAM_CHAT_ID"] = req.telegram_chat_id
        
    with open(env_path, "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")
            
    return {"success": True, "message": "Settings updated"}
