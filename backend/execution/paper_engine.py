import asyncio
import datetime
import logging
from sqlalchemy import select, update, delete
from backend.db.session import async_session_factory, commit_with_retry
from backend.db.models import Position, Trade, AccountBalance, PortfolioSnapshot
from backend.config import settings
from backend.api.websocket import ws_manager

logger = logging.getLogger("alphaforge.paper_engine")

class PaperTradingEngine:
    def __init__(self):
        self.slippage_bps = settings.SLIPPAGE_BPS
        self.commission_per_share = 0.005 # $0.005/share typical broker rate
        self._lock = asyncio.Lock()
        
    async def get_account_summary(self):
        async with async_session_factory() as session:
            acc_res = await session.execute(select(AccountBalance))
            acc = acc_res.scalars().first()
            cash = acc.cash if acc else settings.PAPER_INITIAL_CASH
            
            pos_res = await session.execute(select(Position))
            positions = pos_res.scalars().all()
            
            positions_value = sum(p.market_value for p in positions)
            total_equity = cash + positions_value
            initial_cap = acc.initial_capital if acc else settings.PAPER_INITIAL_CASH
            total_pnl = total_equity - initial_cap
            total_pnl_pct = (total_pnl / initial_cap) * 100 if initial_cap > 0 else 0.0
            
            return {
                "cash": round(cash, 2),
                "positions_value": round(positions_value, 2),
                "total_equity": round(total_equity, 2),
                "initial_capital": round(initial_cap, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "open_positions_count": len(positions)
            }

    async def execute_order(self, symbol: str, side: str, qty: float, current_price: float, reason: str = "", catalyst: str = "", stop_loss_pct: float = None, take_profit_pct: float = None, broker_name: str = "SIMULATED_PAPER"):
        """Executes a simulated paper market order with slippage, commission, and lock protection."""
        symbol = symbol.upper().strip()
        side = side.upper().strip()
        qty = round(float(qty), 4)
        
        if qty <= 0 or current_price <= 0:
            return {"success": False, "error": "Invalid quantity or price"}

        # Calculate execution price with slippage
        slippage_multiplier = 1.0 + (self.slippage_bps / 10000.0) if side == "BUY" else 1.0 - (self.slippage_bps / 10000.0)
        fill_price = round(current_price * slippage_multiplier, 4)
        slippage_cost = round(abs(fill_price - current_price) * qty, 4)
        commission = round(qty * self.commission_per_share, 2)
        total_order_cost = round((fill_price * qty) + commission, 2)

        async with self._lock:
            async with async_session_factory() as session:
                acc_res = await session.execute(select(AccountBalance))
                acc = acc_res.scalars().first()
                if not acc:
                    acc = AccountBalance(cash=settings.PAPER_INITIAL_CASH, initial_capital=settings.PAPER_INITIAL_CASH)
                    session.add(acc)
                    await session.flush()

                pos_res = await session.execute(select(Position).where(Position.symbol == symbol))
                pos = pos_res.scalars().first()

                if side == "BUY":
                    if acc.cash < total_order_cost:
                        return {"success": False, "error": f"Insufficient cash (${acc.cash:,.2f}) for order (${total_order_cost:,.2f})"}
                    
                    # Deduct cash
                    acc.cash -= total_order_cost
                    
                    stop_loss = fill_price * (1.0 - (stop_loss_pct or settings.DEFAULT_STOP_LOSS_PCT))
                    take_profit = fill_price * (1.0 + (take_profit_pct or settings.DEFAULT_TAKE_PROFIT_PCT))
                    
                    if pos:
                        new_qty = pos.qty + qty
                        new_avg_price = ((pos.qty * pos.avg_entry_price) + (qty * fill_price)) / new_qty
                        pos.qty = new_qty
                        pos.avg_entry_price = round(new_avg_price, 4)
                        pos.current_price = fill_price
                        pos.market_value = round(new_qty * fill_price, 2)
                        pos.unrealized_pnl = round(pos.market_value - (new_qty * pos.avg_entry_price), 2)
                        pos.unrealized_pnl_pct = round((pos.unrealized_pnl / (new_qty * pos.avg_entry_price)) * 100, 2)
                        pos.stop_loss = round(stop_loss, 2)
                        pos.take_profit = round(take_profit, 2)
                        pos.updated_at = datetime.datetime.now(datetime.UTC)
                    else:
                        pos = Position(
                            symbol=symbol,
                            qty=qty,
                            avg_entry_price=fill_price,
                            current_price=fill_price,
                            market_value=round(qty * fill_price, 2),
                            unrealized_pnl=0.0,
                            unrealized_pnl_pct=0.0,
                            stop_loss=round(stop_loss, 2),
                            take_profit=round(take_profit, 2),
                            catalyst=catalyst,
                            entry_time=datetime.datetime.now(datetime.UTC),
                            updated_at=datetime.datetime.now(datetime.UTC)
                        )
                        session.add(pos)

                    # Record Trade
                    trade = Trade(
                        symbol=symbol,
                        side="BUY",
                        qty=qty,
                        price=fill_price,
                        slippage=slippage_cost,
                        commission=commission,
                        total_cost=total_order_cost,
                        realized_pnl=0.0,
                        reason=reason,
                        broker=broker_name,
                        timestamp=datetime.datetime.now(datetime.UTC)
                    )
                    session.add(trade)
                    
                elif side == "SELL":
                    if not pos or pos.qty < qty:
                        avail = pos.qty if pos else 0
                        return {"success": False, "error": f"Cannot SELL {qty} of {symbol}. Available: {avail}"}

                    proceeds = (fill_price * qty) - commission
                    cost_basis = pos.avg_entry_price * qty
                    realized_pnl = round(proceeds - cost_basis, 2)

                    acc.cash += proceeds

                    remaining_qty = pos.qty - qty
                    if remaining_qty <= 0.0001:
                        await session.delete(pos)
                    else:
                        pos.qty = remaining_qty
                        pos.current_price = fill_price
                        pos.market_value = round(remaining_qty * fill_price, 2)
                        pos.unrealized_pnl = round(pos.market_value - (remaining_qty * pos.avg_entry_price), 2)
                        pos.unrealized_pnl_pct = round((pos.unrealized_pnl / (remaining_qty * pos.avg_entry_price)) * 100, 2)
                        pos.updated_at = datetime.datetime.now(datetime.UTC)

                    trade = Trade(
                        symbol=symbol,
                        side="SELL",
                        qty=qty,
                        price=fill_price,
                        slippage=slippage_cost,
                        commission=commission,
                        total_cost=round(proceeds, 2),
                        realized_pnl=realized_pnl,
                        reason=reason,
                        broker=broker_name,
                        timestamp=datetime.datetime.now(datetime.UTC)
                    )
                    session.add(trade)

                await commit_with_retry(session)

        # Broadcast update over WebSocket
        summary = await self.get_account_summary()
        await ws_manager.broadcast("TRADE_EXECUTED", {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": fill_price,
            "reason": reason,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
        })
        await ws_manager.broadcast("PORTFOLIO_UPDATE", summary)

        return {
            "success": True,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "fill_price": fill_price,
            "slippage": slippage_cost,
            "commission": commission
        }

    async def update_position_prices(self, price_map: dict):
        """Updates current price and unrealized PnL for active positions from market data."""
        triggered_exits = []
        async with self._lock:
            async with async_session_factory() as session:
                pos_res = await session.execute(select(Position))
                positions = pos_res.scalars().all()
                if not positions:
                    return

                for p in positions:
                    curr_price = price_map.get(p.symbol)
                    if curr_price and curr_price > 0:
                        p.current_price = curr_price
                        p.market_value = round(p.qty * curr_price, 2)
                        p.unrealized_pnl = round(p.market_value - (p.qty * p.avg_entry_price), 2)
                        p.unrealized_pnl_pct = round((p.unrealized_pnl / (p.qty * p.avg_entry_price)) * 100, 2)
                        p.updated_at = datetime.datetime.now(datetime.UTC)

                        # Check stop-loss / take-profit
                        if p.stop_loss and curr_price <= p.stop_loss:
                            triggered_exits.append((p.symbol, p.qty, curr_price, f"STOP_LOSS triggered at ${curr_price:.2f} (Target: ${p.stop_loss:.2f})"))
                        elif p.take_profit and curr_price >= p.take_profit:
                            triggered_exits.append((p.symbol, p.qty, curr_price, f"TAKE_PROFIT reached at ${curr_price:.2f} (Target: ${p.take_profit:.2f})"))

                await commit_with_retry(session)

        # Handle exits if any
        for sym, qty, prc, rsn in triggered_exits:
            logger.info(f"Auto-closing position {sym}: {rsn}")
            await self.execute_order(symbol=sym, side="SELL", qty=qty, current_price=prc, reason=rsn)

    async def record_snapshot(self):
        """Records a point-in-time snapshot for the portfolio equity curve."""
        summary = await self.get_account_summary()
        async with self._lock:
            async with async_session_factory() as session:
                snap = PortfolioSnapshot(
                    total_equity=summary["total_equity"],
                    cash=summary["cash"],
                    positions_value=summary["positions_value"],
                    daily_pnl=summary["total_pnl"],
                    daily_pnl_pct=summary["total_pnl_pct"],
                    timestamp=datetime.datetime.now(datetime.UTC)
                )
                session.add(snap)
                await commit_with_retry(session)

paper_engine = PaperTradingEngine()
