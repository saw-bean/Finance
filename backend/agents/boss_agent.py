import datetime
import logging
from typing import Dict, Any, Optional
from sqlalchemy import select

from backend.agents.base import BaseAgent
from backend.agents.registry import agent_registry
from backend.db.session import async_session_factory
from backend.db.models import AgentState, Trade, Position, AccountBalance, CatalystPerformance
from backend.api.websocket import ws_manager
from backend.config import settings

logger = logging.getLogger("alphaforge.boss_agent")


class BossArchitectAgent(BaseAgent):
    """
    Fund auditor. Reports account, win rate, catalyst stats and agent errors straight from the
    database. It does not change trades, balances or code.
    """
    def __init__(self):
        super().__init__(
            name="boss_agent",
            display_name="Fund Auditor",
            interval_seconds=60
        )
        self.health_score: Optional[float] = None
        self._last_audit_summary: Dict[str, Any] = {}

    async def run_iteration(self):
        audit = await self.conduct_system_audit()
        self._last_audit_summary = audit
        await self.update_status("RUNNING", stats={
            "health_score": audit["health_score"],
            "total_agents": len(agent_registry.list_agents()),
            "win_rate": audit["win_rate"],
            "closed_trades": audit["closed_trades"]
        })

    async def conduct_system_audit(self) -> Dict[str, Any]:
        async with async_session_factory() as session:
            acc = (await session.execute(select(AccountBalance))).scalars().first()
            cash = acc.cash if acc else settings.PAPER_INITIAL_CASH
            initial_cap = acc.initial_capital if acc else settings.PAPER_INITIAL_CASH

            positions = (await session.execute(select(Position).where(Position.qty > 0))).scalars().all()
            pos_val = sum(p.qty * p.current_price for p in positions)
            total_equity = cash + pos_val
            total_pnl = total_equity - initial_cap
            total_pnl_pct = (total_pnl / initial_cap) * 100 if initial_cap > 0 else 0.0

            trades = (await session.execute(select(Trade))).scalars().all()
            closed = [t for t in trades if t.side == "SELL"]
            wins = [t for t in closed if (t.realized_pnl or 0) > 0]
            win_rate = round(len(wins) / len(closed) * 100, 1) if closed else None

            catalysts = (await session.execute(select(CatalystPerformance))).scalars().all()
            agent_states = (await session.execute(select(AgentState))).scalars().all()

        total_errors = sum((a.errors_count or 0) for a in agent_states)
        agents_in_error = [a.name for a in agent_states if a.status == "ERROR"]

        # Health: starts at 100, loses points for drawdown, a losing record and failing agents
        score = 100.0
        if total_pnl_pct < 0:
            score -= min(40.0, abs(total_pnl_pct) * 3)
        if win_rate is not None and win_rate < 50 and len(closed) >= 5:
            score -= 15.0
        score -= min(30.0, len(agents_in_error) * 10)
        self.health_score = round(max(0.0, score), 1)

        recs = []
        if agents_in_error:
            recs.append(f"Agents currently failing: {', '.join(agents_in_error)}. Check the agent logs.")
        if total_pnl_pct <= -settings.MAX_DAILY_DRAWDOWN_PCT * 100:
            recs.append(f"Account is down {total_pnl_pct:.1f}% from initial capital.")
        for p in positions:
            if p.stop_loss and p.current_price and p.current_price <= p.stop_loss * 1.02:
                recs.append(f"{p.symbol} is within 2% of its stop (${p.stop_loss:.2f}).")
        if not closed:
            recs.append("No closed trades yet; win rate and catalyst weights are not meaningful until trades close.")

        audit = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "health_score": self.health_score,
            "account": {
                "cash": round(cash, 2),
                "positions_value": round(pos_val, 2),
                "total_equity": round(total_equity, 2),
                "initial_capital": round(initial_cap, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "open_positions": len(positions)
            },
            "win_rate": win_rate,
            "total_trades": len(trades),
            "closed_trades": len(closed),
            "catalyst_ratings": {
                c.catalyst_type: {
                    "win_rate": round(c.wins / c.total_trades * 100, 1) if c.total_trades else None,
                    "weight": round(c.calibrated_weight, 2),
                    "trades": c.total_trades
                }
                for c in catalysts
            },
            "agent_performance": [
                {"name": a.name, "display_name": a.display_name, "status": a.status,
                 "signals": a.signals_generated, "errors": a.errors_count}
                for a in agent_states
            ],
            "total_agent_errors": total_errors,
            "recommendations": recs
        }
        await ws_manager.broadcast("BOSS_AUDIT_UPDATE", audit)
        return audit

    def get_summary(self) -> Dict[str, Any]:
        return self._last_audit_summary or {"health_score": self.health_score}

boss_agent = BossArchitectAgent()
