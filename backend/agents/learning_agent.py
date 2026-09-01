import datetime
import logging
from sqlalchemy import select, desc
from backend.agents.base import BaseAgent
from backend.db.session import async_session_factory, commit_with_retry
from backend.db.models import Trade, TradeReflection, CatalystPerformance
from backend.api.websocket import ws_manager

logger = logging.getLogger("alphaforge.learning_agent")

class LearningReflectionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="learning_agent",
            display_name="Autonomous Learning & Reflection Engine",
            interval_seconds=45
        )
        self.reflected_trade_ids = set()

    async def run_iteration(self):
        await self.log("INFO", "Reviewing trade execution history and updating catalyst win-rate models...")
        
        async with async_session_factory() as session:
            # 1. Fetch all existing reflected trade IDs to avoid duplicate analysis
            refl_res = await session.execute(select(TradeReflection.trade_id))
            existing_refl_ids = set(refl_res.scalars().all())
            self.reflected_trade_ids.update(existing_refl_ids)
            
            # 2. Fetch un-reflected SELL trades (closed positions)
            trades_res = await session.execute(
                select(Trade)
                .where(Trade.side == "SELL")
                .order_by(Trade.timestamp.asc())
            )
            closed_trades = trades_res.scalars().all()
            
            new_reflections = 0
            for trade in closed_trades:
                if trade.id in self.reflected_trade_ids:
                    continue
                
                # Analyze this closed trade
                await self._analyze_and_learn_from_trade(session, trade)
                self.reflected_trade_ids.add(trade.id)
                new_reflections += 1

            # 3. Recalculate catalyst performance aggregates
            await self._update_catalyst_performances(session)
            
            await commit_with_retry(session)

        if new_reflections > 0:
            await self.log("ACTION", f"Generated {new_reflections} new trade post-mortem reflections & recalibrated weights.")
        await self.update_status("RUNNING", stats={"total_reflections": len(self.reflected_trade_ids), "last_batch": new_reflections})

    async def _analyze_and_learn_from_trade(self, session, sell_trade: Trade):
        """Analyzes a closed trade, extracts catalyst, and generates structured reflection."""
        # Find matching BUY trade to determine entry price and catalyst
        buy_res = await session.execute(
            select(Trade)
            .where(Trade.symbol == sell_trade.symbol, Trade.side == "BUY")
            .order_by(Trade.timestamp.desc())
        )
        buy_trade = buy_res.scalars().first()
        
        entry_price = buy_trade.price if buy_trade else sell_trade.price
        exit_price = sell_trade.price
        pnl = sell_trade.realized_pnl
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0.0
        
        # Determine catalyst from trade rationale
        catalyst = "MANUAL_EXECUTION"
        if "FORENSIC" in sell_trade.reason.upper() or (buy_trade and "FORENSIC" in buy_trade.reason.upper()):
            catalyst = "FORENSIC_HIGH_QUALITY"
        elif "FORM 4" in sell_trade.reason.upper() or (buy_trade and "FORM 4" in buy_trade.reason.upper()):
            catalyst = "SEC_FORM4_CLUSTER_BUY"
        elif "CONTRACT" in sell_trade.reason.upper() or (buy_trade and "CONTRACT" in buy_trade.reason.upper()):
            catalyst = "GOV_CONTRACT_AWARD"
        elif "SQUEEZE" in sell_trade.reason.upper() or (buy_trade and "SQUEEZE" in buy_trade.reason.upper()):
            catalyst = "SHORT_SQUEEZE_SETUP"
        elif "RED FLAG" in sell_trade.reason.upper() or (buy_trade and "RED FLAG" in buy_trade.reason.upper()):
            catalyst = "ACCOUNTING_RED_FLAG"

        outcome = "WIN" if pnl > 0.01 else ("LOSS" if pnl < -0.01 else "BREAKEVEN")
        
        # Generate plain English lesson
        if outcome == "WIN":
            summary = f"Profitable exit on ${sell_trade.symbol} (+{pnl_pct:.2f}% / +${pnl:.2f})."
            lesson = f"The {catalyst} thesis provided strong price support. Execution filled cleanly at ${exit_price:.2f}."
        elif outcome == "LOSS":
            summary = f"Loss on ${sell_trade.symbol} ({pnl_pct:.2f}% / -${abs(pnl):.2f})."
            lesson = f"Stop-loss was triggered. Catalyst momentum was insufficient to overcome prevailing market drag."
        else:
            summary = f"Breakeven exit on ${sell_trade.symbol} ($0.00 PnL)."
            lesson = f"Position closed near cost basis with minimal slippage impact."

        reflection = TradeReflection(
            trade_id=sell_trade.id,
            symbol=sell_trade.symbol,
            side="SELL",
            catalyst=catalyst,
            entry_price=entry_price,
            exit_price=exit_price,
            realized_pnl=pnl,
            pnl_pct=round(pnl_pct, 2),
            outcome=outcome,
            reflection_summary=summary,
            lessons_learned=lesson,
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        session.add(reflection)
        
        await ws_manager.broadcast("TRADE_REFLECTION", {
            "symbol": sell_trade.symbol,
            "outcome": outcome,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "catalyst": catalyst,
            "summary": summary,
            "lesson": lesson,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
        })

    async def _update_catalyst_performances(self, session):
        """Calculates Bayesian smoothed win rates and dynamic conviction weights per catalyst."""
        refl_res = await session.execute(select(TradeReflection))
        reflections = refl_res.scalars().all()
        
        # Group by catalyst
        stats_by_cat = {}
        for r in reflections:
            cat = r.catalyst or "MANUAL_EXECUTION"
            if cat not in stats_by_cat:
                stats_by_cat[cat] = {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "total_pct": 0.0}
            
            stats_by_cat[cat]["trades"] += 1
            if r.outcome == "WIN":
                stats_by_cat[cat]["wins"] += 1
            elif r.outcome == "LOSS":
                stats_by_cat[cat]["losses"] += 1
            stats_by_cat[cat]["total_pnl"] += r.realized_pnl
            stats_by_cat[cat]["total_pct"] += r.pnl_pct

        # Update database records
        for cat, s in stats_by_cat.items():
            perf_res = await session.execute(select(CatalystPerformance).where(CatalystPerformance.catalyst_type == cat))
            perf = perf_res.scalars().first()
            if not perf:
                perf = CatalystPerformance(
                    catalyst_type=cat,
                    display_name=cat.replace("_", " ").title(),
                    total_trades=0,
                    wins=0,
                    losses=0,
                    win_rate=0.50,
                    total_pnl=0.0,
                    avg_return_pct=0.0,
                    calibrated_weight=1.0
                )
                session.add(perf)
                
            perf.total_trades = s["trades"]
            perf.wins = s["wins"]
            perf.losses = s["losses"]
            perf.total_pnl = round(s["total_pnl"], 2)
            perf.avg_return_pct = round(s["total_pct"] / s["trades"], 2) if s["trades"] > 0 else 0.0
            
            # Bayesian smoothed win rate: (Wins + 1) / (Total + 2) [Beta(1,1) prior]
            smoothed_win_rate = (s["wins"] + 1) / (s["trades"] + 2)
            perf.win_rate = round(smoothed_win_rate, 3)
            
            # Calibrate conviction multiplier between 0.5x and 1.5x
            # 50% win rate -> 1.0x weight
            # 80% win rate -> 1.4x weight
            # 20% win rate -> 0.6x weight
            calibrated_weight = max(0.50, min(1.50, round(smoothed_win_rate / 0.50, 2)))
            perf.calibrated_weight = calibrated_weight
            perf.last_updated = datetime.datetime.now(datetime.UTC)

learning_agent = LearningReflectionAgent()
