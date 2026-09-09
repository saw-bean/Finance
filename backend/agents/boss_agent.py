import asyncio
import datetime
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, desc

from backend.agents.base import BaseAgent
from backend.agents.registry import agent_registry
from backend.agents.boss_coder import boss_coder
from backend.db.session import async_session_factory, commit_with_retry
from backend.db.models import (
    AgentState, AgentLog, Trade, Position, AccountBalance, 
    TradeReflection, CatalystPerformance, BossDirective, SystemEvolution
)
from backend.api.websocket import ws_manager
from backend.config import settings

logger = logging.getLogger("alphaforge.boss_agent")

class BossArchitectAgent(BaseAgent):
    """
    Autonomous Chief Architect & Fund Boss Agent.
    - Executive Oversight: Audits hedge fund swarm performance 24/7.
    - Self-Coding & Strategy Synthesis: Writes, validates, and hot-deploys new strategy agents.
    - Dynamic Swarm Governance: Tunes risk parameters, adjusts position runner targets, and spawns sub-agents.
    """
    def __init__(self):
        super().__init__(
            name="boss_agent",
            display_name="Chief Architect & Fund Boss",
            interval_seconds=60
        )
        self.health_score: float = 95.0
        self.deployed_strategies: set = set()
        self.active_directives: Dict[str, Any] = {}
        self._last_audit_summary: Dict[str, Any] = {}

    async def run_iteration(self):
        await self.log("INFO", "Conducting full fund performance audit and swarm strategy evaluation...")
        
        audit = await self.conduct_system_audit()
        self._last_audit_summary = audit
        
        # Determine and execute autonomous enhancements
        await self._evaluate_and_evolve(audit)
        
        await self.update_status(
            "RUNNING", 
            stats={
                "health_score": round(self.health_score, 1),
                "total_agents": len(agent_registry.list_agents()),
                "deployed_strategies": len(self.deployed_strategies),
                "active_directives": len(self.active_directives)
            }
        )

    async def conduct_system_audit(self) -> Dict[str, Any]:
        """Performs deep empirical performance analysis across all trading metrics."""
        audit_data = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "health_score": 95.0,
            "account": {},
            "positions": [],
            "win_rate": 0.5,
            "total_trades": 0,
            "catalyst_ratings": {},
            "agent_performance": [],
            "recommendations": []
        }
        
        async with async_session_factory() as session:
            # 1. Account & Portfolio
            acc_res = await session.execute(select(AccountBalance))
            acc = acc_res.scalars().first()
            cash = acc.cash if acc else 100.0
            initial_cap = acc.initial_capital if acc else 100.0
            
            pos_res = await session.execute(select(Position).where(Position.qty > 0))
            positions = pos_res.scalars().all()
            
            pos_val = sum((p.qty * p.current_price) for p in positions)
            total_equity = cash + pos_val
            total_pnl = total_equity - initial_cap
            total_pnl_pct = (total_pnl / initial_cap) * 100 if initial_cap > 0 else 0.0
            
            audit_data["account"] = {
                "cash": round(cash, 2),
                "positions_value": round(pos_val, 2),
                "total_equity": round(total_equity, 2),
                "initial_capital": round(initial_cap, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "open_positions": len(positions)
            }
            
            # 2. Trade win rates
            trades_res = await session.execute(select(Trade))
            trades = trades_res.scalars().all()
            closed_trades = [t for t in trades if t.side == "SELL"]
            winning_trades = [t for t in closed_trades if (t.realized_pnl or 0) > 0]
            win_rate = (len(winning_trades) / len(closed_trades)) if closed_trades else 0.60
            
            audit_data["total_trades"] = len(trades)
            audit_data["win_rate"] = round(win_rate * 100, 1)
            
            # 3. Catalyst calibrations
            cat_res = await session.execute(select(CatalystPerformance))
            catalysts = cat_res.scalars().all()
            audit_data["catalyst_ratings"] = {
                c.catalyst_type: {
                    "win_rate": round(c.win_rate * 100, 1),
                    "weight": round(c.calibrated_weight, 2),
                    "trades": c.total_trades
                }
                for c in catalysts
            }
            
            # 4. Swarm Agents
            agent_res = await session.execute(select(AgentState))
            agent_states = agent_res.scalars().all()
            total_errors = sum((a.errors_count or 0) for a in agent_states)
            
            audit_data["agent_performance"] = [
                {
                    "name": a.name,
                    "display_name": a.display_name,
                    "status": a.status,
                    "signals": a.signals_generated,
                    "errors": a.errors_count
                }
                for a in agent_states
            ]
            
            # 5. Compute System Health Score (0 - 100)
            score = 100.0
            if total_pnl_pct < 0:
                score -= min(25.0, abs(total_pnl_pct) * 3)
            elif total_pnl_pct > 0:
                score += min(10.0, total_pnl_pct * 2)
                
            if win_rate < 0.50 and len(closed_trades) > 3:
                score -= 15.0
                
            if total_errors > 0:
                score -= min(15.0, total_errors * 2)
                
            self.health_score = max(50.0, min(100.0, score))
            audit_data["health_score"] = round(self.health_score, 1)
            
            # Recommendations
            recs = []
            if total_pnl_pct > 5.0:
                recs.append("Portfolio running in strong alpha regime. Increase runner profit target to +25%.")
            if any(p.unrealized_pnl_pct > 7.0 for p in positions):
                recs.append("High-performing positions detected (e.g. ASTS). Protect gains with Ratchet Breakeven stops.")
            if len(positions) >= 6:
                recs.append("Portfolio fully diversified across 6 quality catalysts. Prioritize sniper conviction.")
            audit_data["recommendations"] = recs

        # Broadcast live audit
        await ws_manager.broadcast("BOSS_AUDIT_UPDATE", audit_data)
        return audit_data

    async def _evaluate_and_evolve(self, audit: Dict[str, Any]):
        """Evaluates whether to synthesize new strategies or adjust system directives."""
        
        # 1. Autonomous Strategy 1: Biotech & FDA PDUFA Catalyst Sniper
        if "BIOTECH_FDA" not in self.deployed_strategies:
            await self.log("ACTION", "Boss Analysis: Identifying high-upside biotech FDA catalyst niche. Synthesizing sub-agent...")
            success, msg, agent_inst = await self.synthesize_and_deploy_agent(
                strategy_type="BIOTECH_FDA",
                custom_params={"target": "PDUFA_Milestones"}
            )
            if success:
                self.deployed_strategies.add("BIOTECH_FDA")
                await self._set_directive("BIOTECH_FDA_STRATEGY", "ACTIVE", "Autonomous Biotech Catalyst Sub-Agent Deployed")

        # 2. Autonomous Strategy 2: Earnings & Guidance Acceleration
        elif "EARNINGS_ACCEL" not in self.deployed_strategies:
            await self.log("ACTION", "Boss Analysis: Expanding coverage to quarterly EPS surprise velocity. Synthesizing sub-agent...")
            success, msg, agent_inst = await self.synthesize_and_deploy_agent(
                strategy_type="EARNINGS_ACCELERATION",
                custom_params={"target": "EPS_Surprise_Velocity"}
            )
            if success:
                self.deployed_strategies.add("EARNINGS_ACCEL")
                await self._set_directive("EARNINGS_ACCEL_STRATEGY", "ACTIVE", "Autonomous Earnings Acceleration Sniper Deployed")

    async def synthesize_and_deploy_agent(
        self, 
        strategy_type: str, 
        custom_params: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[BaseAgent]]:
        """
        Synthesizes Python code for a new agent, validates AST, executes sandbox tests,
        and deploys it directly into the running swarm.
        """
        await self.log("INFO", f"Synthesizing Python source code for strategy '{strategy_type}'...")
        
        code, class_name, file_name = boss_coder.generate_strategy_code(strategy_type, custom_params)
        
        # 1. AST Validation
        is_valid_ast, ast_msg = boss_coder.validate_code_ast(code, expected_class=class_name)
        if not is_valid_ast:
            await self.log("ERROR", f"Code validation failed: {ast_msg}")
            return False, ast_msg, None
            
        # 2. Sandbox Verification
        sandbox_ok, sandbox_msg, stats = await boss_coder.sandbox_verify(code, class_name)
        if not sandbox_ok:
            await self.log("ERROR", f"Sandbox verification failed: {sandbox_msg}")
            return False, sandbox_msg, None
            
        # 3. Save to disk
        file_path = boss_coder.save_and_deploy_agent_file(file_name, code)
        
        # 4. Dynamically load and register in swarm
        try:
            agent_inst = await agent_registry.spawn_dynamic_agent_from_file(
                file_path=file_path,
                class_name=class_name,
                name=stats.get("agent_name", f"{strategy_type.lower()}_agent"),
                display_name=stats.get("display_name", f"{strategy_type} Agent"),
                interval_seconds=stats.get("interval_seconds", 60)
            )
        except Exception as e:
            logger.error(f"Failed to dynamically boot agent: {e}", exc_info=True)
            return False, str(e), None

        # 5. Persist to SystemEvolution database
        try:
            async with async_session_factory() as session:
                evolution = SystemEvolution(
                    action_type="AGENT_SPAWNED",
                    title=f"Boss Synthesized & Deployed: {stats.get('display_name')}",
                    description=f"Autonomously generated and verified Python agent for strategy '{strategy_type}'. AST & sandbox tests passed.",
                    code_path=str(file_path),
                    code_content=code,
                    ast_verified=True,
                    sandbox_passed=True,
                    target_agent=stats.get("agent_name"),
                    status="ACTIVE",
                    impact_metrics=json.dumps({"sandbox_stats": stats})
                )
                session.add(evolution)
                await commit_with_retry(session)
        except Exception as e:
            logger.error(f"Error persisting evolution record: {e}")

        await self.log("ACTION", f"🚀 Boss successfully deployed and booted agent: {stats.get('display_name')}")
        return True, "Agent Successfully Synthesized, Tested & Launched", agent_inst

    async def _set_directive(self, key: str, value: Any, description: str):
        """Sets an active Boss directive in the database."""
        self.active_directives[key] = value
        try:
            async with async_session_factory() as session:
                res = await session.execute(select(BossDirective).where(BossDirective.directive_key == key))
                directive = res.scalars().first()
                if not directive:
                    directive = BossDirective(
                        directive_key=key,
                        category="AUTONOMOUS_GOVERNANCE",
                        value=json.dumps(value),
                        description=description,
                        active=True
                    )
                    session.add(directive)
                else:
                    directive.value = json.dumps(value)
                    directive.description = description
                    directive.active = True
                await commit_with_retry(session)
        except Exception as e:
            logger.error(f"Error recording BossDirective: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Returns the latest executive audit summary."""
        return self._last_audit_summary or {
            "health_score": self.health_score,
            "deployed_strategies": list(self.deployed_strategies),
            "active_directives": self.active_directives
        }

# Global Singleton
boss_agent = BossArchitectAgent()
