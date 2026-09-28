import datetime

import pandas as pd
import pytest
from sqlalchemy import select, delete

from backend.analytics.metrics import return_stats, trade_stats
from backend.db.models import AccountBalance, Position, Trade, CashLedger
from backend.db.session import init_db, async_session_factory, commit_with_retry
from backend.execution.paper_engine import paper_engine, modeled_quote
from backend.market.data import Quote, sell_fees
from backend.agents.mean_reversion_agent import rsi


async def _reset(cash=1000.0):
    await init_db()
    async with async_session_factory() as s:
        await s.execute(delete(Position))
        await s.execute(delete(Trade))
        await s.execute(delete(CashLedger))
        acc = (await s.execute(select(AccountBalance))).scalars().first()
        acc.cash, acc.initial_capital = cash, cash
        await commit_with_retry(s)


def _quote(sym, bid, ask, spf=None):
    return Quote(symbol=sym, bid=bid, ask=ask, last=(bid + ask) / 2, source="LIVE_QUOTE", adv_dollars=1e9,
                 exchange="NMS", quote_type="EQUITY", sector="Technology", short_pct_float=spf)


def test_sell_fees_round_up_to_cents():
    # $1,000 sale of 10 shares: SEC fee $0.0278 -> $0.03, TAF $0.00166 -> $0.01
    assert sell_fees(1000.0, 10) == pytest.approx(0.04)


@pytest.mark.asyncio
async def test_short_then_cover_pnl_fees_and_cash():
    await _reset()
    r = await paper_engine.execute_order("SHRT", "SHORT", 10, quote=_quote("SHRT", 49.99, 50.01), catalyst="TEST")
    assert r["success"] and r["fill_price"] == 49.99       # short sale fills at the bid
    fees = sell_fees(499.9, 10)
    summary = await paper_engine.get_account_summary()
    assert summary["cash"] == pytest.approx(1000 + 499.9 - fees, abs=0.01)
    assert summary["short_count"] == 1

    c = await paper_engine.execute_order("SHRT", "COVER", 10, quote=_quote("SHRT", 44.99, 45.01))
    assert c["success"] and c["fill_price"] == 45.01       # cover fills at the ask
    assert c["realized_pnl"] == pytest.approx((499.9 - fees) - 450.1, abs=0.001)
    summary = await paper_engine.get_account_summary()
    assert summary["open_positions_count"] == 0
    assert summary["total_equity"] == pytest.approx(1000 + c["realized_pnl"], abs=0.01)


@pytest.mark.asyncio
async def test_shorts_are_whole_shares_and_sides_dont_mix():
    await _reset()
    assert not (await paper_engine.execute_order("FRAC", "SHORT", 0.5, quote=_quote("FRAC", 10, 10.01)))["success"]
    assert (await paper_engine.execute_order("MIX", "BUY", 1, quote=_quote("MIX", 10, 10.01)))["success"]
    assert not (await paper_engine.execute_order("MIX", "SHORT", 1, quote=_quote("MIX", 10, 10.01)))["success"]


@pytest.mark.asyncio
async def test_short_stop_triggers_cover():
    await _reset()
    await paper_engine.execute_order("STOP", "SHORT", 2, quote=_quote("STOP", 20, 20.02), stop_loss_pct=0.05)
    await paper_engine.update_position_prices({"STOP": 21.5})  # > 20 * 1.05
    async with async_session_factory() as s:
        assert (await s.execute(select(Position).where(Position.symbol == "STOP"))).scalars().first() is None
        cover = (await s.execute(select(Trade).where(Trade.symbol == "STOP", Trade.side == "COVER"))).scalars().first()
    assert cover is not None and "STOP" in cover.reason


@pytest.mark.asyncio
async def test_borrow_fee_accrues_per_day():
    await _reset()
    await paper_engine.execute_order("BORR", "SHORT", 10, quote=_quote("BORR", 10, 10.01, spf=0.35))
    async with async_session_factory() as s:
        p = (await s.execute(select(Position).where(Position.symbol == "BORR"))).scalars().first()
        assert p.borrow_rate == 0.20                      # hard to borrow
        p.entry_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=3)
        await commit_with_retry(s)
    before = (await paper_engine.get_account_summary())["cash"]
    await paper_engine.accrue_borrow_fees()
    await paper_engine.accrue_borrow_fees()               # idempotent within the day
    after = (await paper_engine.get_account_summary())["cash"]
    assert before - after == pytest.approx(100.0 * 0.20 / 360 * 3, abs=0.01)


def test_return_stats_drawdown_and_benchmark():
    idx = pd.bdate_range("2026-01-05", periods=6)
    equity = pd.Series([101, 103, 99, 100, 104, 106], index=idx, dtype=float)
    bench = pd.Series([400, 404, 412, 404, 408, 416, 424], index=pd.bdate_range("2026-01-02", periods=7), dtype=float)
    st = return_stats(equity, 100.0, bench, rf_annual=0.0)
    assert st["total_return"] == pytest.approx(0.06)
    assert st["max_drawdown"] == pytest.approx(1 - 99 / 103, abs=1e-4)
    assert st["current_drawdown"] == 0
    assert st["annualized_return"] is None               # fewer than 20 days
    assert st["benchmark_return"] == pytest.approx(424 / 400 - 1, abs=1e-4)  # day 1 measured from prior close
    assert "beta" in st and st["sharpe_ratio"] is not None


def test_trade_stats_profit_factor():
    t0 = datetime.datetime(2026, 1, 1)
    mk = lambda side, pnl, d: Trade(symbol="X", side=side, qty=1, price=1, realized_pnl=pnl, timestamp=t0 + datetime.timedelta(days=d))
    st = trade_stats([mk("BUY", 0, 0), mk("SELL", 3.0, 2), mk("SHORT", 0, 3), mk("COVER", -1.0, 4)])
    assert st["closed_trades"] == 2 and st["win_rate"] == 0.5
    assert st["profit_factor"] == 3.0
    assert st["long_win_rate"] == 1.0 and st["short_win_rate"] == 0.0
    assert st["average_holding_days"] == pytest.approx(1.5)


def test_rsi2_extremes():
    down = pd.Series([100, 99, 97, 94, 90, 85], dtype=float)
    assert rsi(down).iloc[-1] < 5
    assert rsi(-down + 200).iloc[-1] > 95
