"""Simulated long/short broker.

Fill model (per order):
- Buys and covers pay the ask, sells and short sales receive the bid. The quote is Yahoo's live
  NBBO when it is sane, otherwise a liquidity-based modeled spread around the last trade.
- Commission $0 (Alpaca-style). Every sale (long sell or short sale) pays the SEC Section 31 fee
  and the FINRA TAF, rounded up to the cent.
- Shorts must be whole shares (no broker lends fractional shares); longs may be fractional.
- Short positions accrue a daily borrow fee on their market value (see accrue_borrow_fees).
- Positions have stop-loss, take-profit, trailing stops and an optional time stop (exit_by).
"""
import asyncio
import datetime
import logging
from typing import Optional

from sqlalchemy import select, func

from backend.api.websocket import ws_manager
from backend.config import settings
from backend.db.models import Position, Trade, AccountBalance, PortfolioSnapshot, CashLedger
from backend.db.session import async_session_factory, commit_with_retry
from backend.market.data import Quote, get_quote, sell_fees, borrow_rate, modeled_half_spread_bps, ny_today
from backend.notifications.telegram import telegram_notifier

logger = logging.getLogger("alphaforge.paper_engine")

OPEN_SIDES = {"BUY": "LONG", "SHORT": "SHORT"}
CLOSE_SIDES = {"SELL": "LONG", "COVER": "SHORT"}


def round_price(p: float) -> float:
    """Cents for normal stocks; 4 decimals below $1 so a sub-dollar stop isn't rounded onto the price."""
    return round(p, 2) if p >= 1 else round(p, 4)


def modeled_quote(symbol: str, price: float) -> Quote:
    half = modeled_half_spread_bps(None if price <= 0 else 1e8) / 10_000
    return Quote(symbol=symbol, bid=price * (1 - half), ask=price * (1 + half), last=price,
                 source="MODELED_SPREAD", adv_dollars=None, exchange=None, quote_type=None,
                 sector=None, short_pct_float=None)


class PaperTradingEngine:
    def __init__(self):
        self.commission_per_order = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    async def get_account_summary(self):
        async with async_session_factory() as session:
            acc = (await session.execute(select(AccountBalance))).scalars().first()
            cash = acc.cash if acc else settings.PAPER_INITIAL_CASH
            positions = (await session.execute(select(Position))).scalars().all()
            initial_cap = acc.initial_capital if acc else settings.PAPER_INITIAL_CASH

        long_value = sum(p.market_value for p in positions if p.qty > 0)
        short_value = -sum(p.market_value for p in positions if p.qty < 0)  # positive number
        total_equity = cash + long_value - short_value
        total_pnl = total_equity - initial_cap
        eq = total_equity if total_equity > 0 else 1.0
        return {
            "cash": round(cash, 2),
            "positions_value": round(long_value - short_value, 2),
            "long_value": round(long_value, 2),
            "short_value": round(short_value, 2),
            "gross_exposure": round((long_value + short_value) / eq, 4),
            "net_exposure": round((long_value - short_value) / eq, 4),
            "total_equity": round(total_equity, 2),
            "initial_capital": round(initial_cap, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round((total_pnl / initial_cap) * 100 if initial_cap > 0 else 0.0, 2),
            "open_positions_count": len(positions),
            "long_count": sum(1 for p in positions if p.qty > 0),
            "short_count": sum(1 for p in positions if p.qty < 0),
        }

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def execute_order(self, symbol: str, side: str, qty: float, current_price: float = None,
                            reason: str = "", catalyst: str = "", stop_loss_pct: float = None,
                            take_profit_pct: float = None, horizon_days: Optional[float] = None,
                            agent_name: str = "", quote: Optional[Quote] = None,
                            broker_name: str = "SIMULATED_PAPER"):
        """Fills a market order against the quote. side: BUY, SELL, SHORT or COVER."""
        symbol = symbol.upper().strip()
        side = side.upper().strip()
        if side not in OPEN_SIDES and side not in CLOSE_SIDES:
            return {"success": False, "error": f"Unknown side {side}"}
        if quote is None:
            quote = modeled_quote(symbol, current_price) if current_price else await asyncio.to_thread(get_quote, symbol)
        if quote is None or quote.last <= 0:
            return {"success": False, "error": f"No quote for {symbol}"}

        qty = float(qty)
        if side in ("SHORT", "COVER"):
            qty = float(int(qty))  # stock loan is whole shares only
        else:
            qty = round(qty, 4)
        if qty <= 0:
            return {"success": False, "error": "Quantity must be positive" + (" (shorts need whole shares)" if side == "SHORT" else "")}

        buying = side in ("BUY", "COVER")
        fill = quote.ask if buying else quote.bid
        notional = fill * qty
        fees = 0.0 if buying else sell_fees(notional, qty)
        spread_paid = abs(fill - quote.mid) * qty
        now = datetime.datetime.now(datetime.UTC)
        sl_pct = stop_loss_pct if stop_loss_pct is not None else settings.DEFAULT_STOP_LOSS_PCT
        tp_pct = take_profit_pct if take_profit_pct is not None else settings.DEFAULT_TAKE_PROFIT_PCT

        realized = 0.0
        entry_price = None
        async with self._lock:
            async with async_session_factory() as session:
                acc = (await session.execute(select(AccountBalance))).scalars().first()
                if not acc:
                    acc = AccountBalance(cash=settings.PAPER_INITIAL_CASH, initial_capital=settings.PAPER_INITIAL_CASH)
                    session.add(acc)
                    await session.flush()
                pos = (await session.execute(select(Position).where(Position.symbol == symbol))).scalars().first()

                if side in OPEN_SIDES:
                    want = OPEN_SIDES[side]
                    if pos and _side(pos) != want:
                        return {"success": False, "error": f"{symbol} has an open {_side(pos)} position; close it first"}
                    if side == "BUY" and acc.cash < notional:
                        return {"success": False, "error": f"Insufficient cash (${acc.cash:,.2f}) for ${notional:,.2f}"}

                    # Cash: buys pay notional; short sales receive proceeds net of fees
                    net_per_share = fill if side == "BUY" else (notional - fees) / qty
                    acc.cash += -notional if side == "BUY" else (notional - fees)
                    signed = qty if side == "BUY" else -qty
                    if side == "BUY":
                        stop, target = fill * (1 - sl_pct), fill * (1 + tp_pct)
                    else:
                        stop, target = fill * (1 + sl_pct), fill * (1 - tp_pct)
                    exit_by = now + datetime.timedelta(days=horizon_days) if horizon_days else None

                    if pos:
                        new_qty = pos.qty + signed
                        pos.avg_entry_price = round((abs(pos.qty) * pos.avg_entry_price + qty * net_per_share) / abs(new_qty), 6)
                        pos.qty = new_qty
                        if exit_by and (pos.exit_by is None or exit_by > _aware(pos.exit_by)):
                            pos.exit_by = exit_by
                    else:
                        pos = Position(symbol=symbol, qty=signed, avg_entry_price=round(net_per_share, 6),
                                       catalyst=catalyst, agent_name=agent_name, side=want, entry_time=now,
                                       sector=quote.sector, exit_by=exit_by, extreme_price=fill,
                                       borrow_rate=borrow_rate(quote) if side == "SHORT" else 0.0)
                        session.add(pos)
                    pos.stop_loss = round_price(stop)
                    pos.take_profit = round_price(target)
                    self._mark(pos, fill, now)
                    entry_price = pos.avg_entry_price
                else:
                    want = CLOSE_SIDES[side]
                    if not pos or _side(pos) != want or abs(pos.qty) + 1e-9 < qty:
                        have = abs(pos.qty) if pos and _side(pos) == want else 0
                        return {"success": False, "error": f"Cannot {side} {qty} {symbol}; {want.lower()} shares held: {have}"}
                    entry_price = pos.avg_entry_price
                    if side == "SELL":
                        realized = (notional - fees) - entry_price * qty
                        acc.cash += notional - fees
                    else:
                        realized = entry_price * qty - notional
                        acc.cash -= notional
                    remaining = abs(pos.qty) - qty
                    if remaining <= 1e-4:
                        await session.delete(pos)
                    else:
                        pos.qty = remaining if want == "LONG" else -remaining
                        self._mark(pos, fill, now)

                session.add(Trade(
                    symbol=symbol, side=side, qty=qty, price=round(fill, 6), slippage=round(spread_paid, 6),
                    commission=self.commission_per_order, fees=fees, total_cost=round(notional, 4),
                    realized_pnl=round(realized, 4), reason=reason, broker=broker_name, timestamp=now,
                    catalyst=catalyst or (pos.catalyst if pos else ""),
                    # Closes are credited to the agent that opened the position, for attribution
                    agent_name=(pos.agent_name if side in CLOSE_SIDES and pos and pos.agent_name else agent_name),
                    mid_price=round(quote.mid, 6), quote_source=quote.source,
                ))
                await commit_with_retry(session)

        summary = await self.get_account_summary()
        await ws_manager.broadcast("TRADE_EXECUTED", {"symbol": symbol, "side": side, "qty": qty, "price": fill,
                                                      "reason": reason, "timestamp": now.isoformat()})
        await ws_manager.broadcast("PORTFOLIO_UPDATE", summary)

        if side in OPEN_SIDES:
            asyncio.create_task(telegram_notifier.send_buy_alert(
                symbol=symbol, qty=qty, price=fill, total_cost=notional, reason=reason, catalyst=catalyst,
                total_equity=summary["total_equity"], cash=summary["cash"], side=side))
        else:
            pct = (realized / (entry_price * qty) * 100) if entry_price else 0.0
            asyncio.create_task(telegram_notifier.send_sell_alert(
                symbol=symbol, qty=qty, exit_price=fill, entry_price=entry_price or fill,
                realized_pnl=realized, pnl_pct=pct, reason=reason, total_equity=summary["total_equity"], side=side))

        return {"success": True, "symbol": symbol, "side": side, "qty": qty, "fill_price": fill,
                "mid_price": quote.mid, "quote_source": quote.source, "fees": fees,
                "spread_cost": spread_paid, "realized_pnl": realized}

    @staticmethod
    def _mark(p: Position, price: float, now) -> None:
        p.current_price = price
        p.market_value = round(p.qty * price, 4)
        p.unrealized_pnl = round((price - p.avg_entry_price) * p.qty, 4)
        basis = abs(p.qty) * p.avg_entry_price
        p.unrealized_pnl_pct = round(p.unrealized_pnl / basis * 100, 2) if basis > 0 else 0.0
        p.updated_at = now

    # ------------------------------------------------------------------
    # Mark-to-market, stops, time stops
    # ------------------------------------------------------------------

    async def update_position_prices(self, price_map: dict):
        """Marks positions to ``price_map`` and closes any that hit a stop, target or time stop."""
        exits = []
        now = datetime.datetime.now(datetime.UTC)
        async with self._lock:
            async with async_session_factory() as session:
                positions = (await session.execute(select(Position))).scalars().all()
                for p in positions:
                    price = price_map.get(p.symbol)
                    if not price or price <= 0:
                        continue
                    # Circuit breaker against bad ticks
                    if p.current_price > 0 and (price < p.current_price * 0.45 or price > p.current_price * 2.5):
                        logger.warning(f"CIRCUIT BREAKER: {p.symbol} tick ${price:.4f} vs ${p.current_price:.4f}; skipped")
                        continue
                    self._mark(p, price, now)
                    is_long = p.qty > 0
                    p.extreme_price = max(p.extreme_price or price, price) if is_long else min(p.extreme_price or price, price)
                    gain = p.unrealized_pnl_pct

                    # Ratchet: breakeven +1% at +8%, then trail 5% from the best price at +15%
                    if gain >= 8.0:
                        be = round_price(p.avg_entry_price * (1.01 if is_long else 0.99))
                        if p.stop_loss is None or (is_long and p.stop_loss < be) or (not is_long and p.stop_loss > be):
                            p.stop_loss = be
                    if gain >= 15.0:
                        trail = round_price(p.extreme_price * (0.95 if is_long else 1.05))
                        if (is_long and trail > (p.stop_loss or 0)) or (not is_long and trail < (p.stop_loss or float("inf"))):
                            p.stop_loss = trail
                        p.take_profit = None

                    close_side = "SELL" if is_long else "COVER"
                    hit_stop = p.stop_loss and (price <= p.stop_loss if is_long else price >= p.stop_loss)
                    hit_target = p.take_profit and (price >= p.take_profit if is_long else price <= p.take_profit)
                    if hit_stop:
                        exits.append((p.symbol, close_side, abs(p.qty), f"STOP at ${price:.2f} (stop ${p.stop_loss:.2f})"))
                    elif hit_target:
                        exits.append((p.symbol, close_side, abs(p.qty), f"TARGET at ${price:.2f} (target ${p.take_profit:.2f})"))
                    elif p.exit_by and now >= _aware(p.exit_by):
                        exits.append((p.symbol, close_side, abs(p.qty), "TIME STOP: signal horizon ended"))
                await commit_with_retry(session)

        for sym, side, qty, why in exits:
            logger.info(f"Auto-closing {sym}: {why}")
            q = await asyncio.to_thread(get_quote, sym) or modeled_quote(sym, price_map[sym])
            await self.execute_order(symbol=sym, side=side, qty=qty, reason=why, agent_name="cio_risk_agent", quote=q)

    # ------------------------------------------------------------------
    # Borrow fees & snapshots
    # ------------------------------------------------------------------

    async def accrue_borrow_fees(self):
        """Charges each short its stock-loan fee: |market value| x annual rate / 360 per calendar day,
        for every day since the last accrual (or since entry). Safe to call repeatedly."""
        today = ny_today()
        async with self._lock:
            async with async_session_factory() as session:
                acc = (await session.execute(select(AccountBalance))).scalars().first()
                shorts = (await session.execute(select(Position).where(Position.qty < 0))).scalars().all()
                for p in shorts:
                    last = (await session.execute(
                        select(func.max(CashLedger.timestamp)).where(CashLedger.kind == "BORROW_FEE", CashLedger.symbol == p.symbol)
                    )).scalar()
                    since = max(_aware(last).date() if last else _aware(p.entry_time).date(),
                                _aware(p.entry_time).date())
                    days = (today - since).days
                    if days <= 0 or not p.borrow_rate:
                        continue
                    fee = round(abs(p.market_value) * p.borrow_rate / 360 * days, 4)
                    acc.cash -= fee
                    session.add(CashLedger(kind="BORROW_FEE", symbol=p.symbol, amount=-fee,
                                           note=f"{days}d at {p.borrow_rate:.2%}/yr on ${abs(p.market_value):.2f}"))
                await commit_with_retry(session)

    async def record_snapshot(self):
        summary = await self.get_account_summary()
        async with self._lock:
            async with async_session_factory() as session:
                session.add(PortfolioSnapshot(
                    total_equity=summary["total_equity"], cash=summary["cash"],
                    positions_value=summary["positions_value"], long_value=summary["long_value"],
                    short_value=summary["short_value"], daily_pnl=summary["total_pnl"],
                    daily_pnl_pct=summary["total_pnl_pct"], timestamp=datetime.datetime.now(datetime.UTC)))
                await commit_with_retry(session)


def _side(p: Position) -> str:
    return "LONG" if p.qty > 0 else "SHORT"


def _aware(dt: datetime.datetime) -> datetime.datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


paper_engine = PaperTradingEngine()
