import asyncio
import datetime
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from sqlalchemy import select, update
from backend.db.session import async_session_factory
from backend.db.models import AgentState, AgentLog, Signal
from backend.api.websocket import ws_manager

logger = logging.getLogger("alphaforge.agent")

class BaseAgent(ABC):
    def __init__(self, name: str, display_name: str, interval_seconds: int = 60):
        self.name = name
        self.display_name = display_name
        self.interval_seconds = interval_seconds
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def log(self, level: str, message: str, ticker: Optional[str] = None):
        """Persists agent log to database and broadcasts via WebSocket."""
        logger.info(f"[{self.display_name}] [{level}] {message}")
        try:
            async with async_session_factory() as session:
                log_entry = AgentLog(
                    agent_name=self.name,
                    level=level,
                    message=message,
                    ticker=ticker,
                    timestamp=datetime.datetime.now(datetime.UTC)
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            logger.error(f"Error persisting log for {self.name}: {e}")
            
        try:
            await ws_manager.broadcast("AGENT_LOG", {
                "agent_name": self.name,
                "display_name": self.display_name,
                "level": level,
                "message": message,
                "ticker": ticker,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            })
        except Exception:
            pass

    async def emit_signal(self, ticker: str, catalyst_type: str, action: str, confidence: float, title: str, summary: str, metadata: Dict[str, Any] = None) -> Signal:
        """Stores a high-conviction signal and alerts via WebSocket."""
        ticker = ticker.upper().strip()
        metadata_str = json.dumps(metadata or {})
        
        sig = Signal(
            ticker=ticker,
            agent_name=self.name,
            catalyst_type=catalyst_type,
            action=action,
            confidence=confidence,
            title=title,
            summary=summary,
            raw_metadata=metadata_str,
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        
        async with async_session_factory() as session:
            session.add(sig)
            
            # Increment agent signal count
            res = await session.execute(select(AgentState).where(AgentState.name == self.name))
            state = res.scalars().first()
            if state:
                state.signals_generated = (state.signals_generated or 0) + 1
                
            await session.commit()
            
        await self.log("ALPHA", f"Generated {action} signal for {ticker} ({catalyst_type}) with confidence {confidence*100:.0f}%", ticker=ticker)
        
        await ws_manager.broadcast("NEW_SIGNAL", {
            "id": getattr(sig, 'id', None),
            "ticker": ticker,
            "agent_name": self.name,
            "agent_display_name": self.display_name,
            "catalyst_type": catalyst_type,
            "action": action,
            "confidence": confidence,
            "title": title,
            "summary": summary,
            "metadata": metadata or {},
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
        })
        return sig

    async def update_status(self, status: str, last_error: Optional[str] = None, stats: Optional[Dict[str, Any]] = None):
        """Updates agent lifecycle status in the database."""
        try:
            async with async_session_factory() as session:
                res = await session.execute(select(AgentState).where(AgentState.name == self.name))
                state = res.scalars().first()
                if state:
                    state.status = status
                    state.last_run = datetime.datetime.now(datetime.UTC)
                    state.next_run = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=self.interval_seconds)
                    if last_error:
                        state.last_error = last_error
                        state.errors_count = (state.errors_count or 0) + 1
                    if stats:
                        state.stats = json.dumps(stats)
                    await session.commit()
                    
            await ws_manager.broadcast("AGENT_STATUS_UPDATE", {
                "agent_name": self.name,
                "display_name": self.display_name,
                "status": status,
                "last_error": last_error,
                "stats": stats or {}
            })
        except Exception as e:
            logger.error(f"Error updating status for {self.name}: {e}")

    async def start(self):
        """Starts the agent background loop."""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Gracefully stops the agent background loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.update_status("IDLE")

    async def _run_loop(self):
        """Main agent worker execution loop with staggered start."""
        await asyncio.sleep(1.0) # Allow server to bind and finish startup
        await self.log("INFO", f"{self.display_name} activated. Loop interval: {self.interval_seconds}s")
        
        while self.running:
            try:
                await self.update_status("POLLING")
                await self.run_iteration()
                await self.update_status("RUNNING")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in agent {self.name}: {e}", exc_info=True)
                await self.log("ERROR", f"Exception during execution: {str(e)}")
                await self.update_status("ERROR", last_error=str(e))
            
            # Wait for next interval
            await asyncio.sleep(self.interval_seconds)

    @abstractmethod
    async def run_iteration(self):
        """Subclasses must implement this method."""
        pass
