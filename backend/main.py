import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings, BASE_DIR
from backend.db.session import init_db
from backend.api.routes import router as api_router
from backend.api.websocket import ws_manager
from backend.api.auth import router as auth_router, auth_middleware, websocket_authorized

# Import Autonomous Swarm Agents & Registry
from backend.agents.registry import agent_registry
from backend.agents.sec_edgar import sec_agent
from backend.agents.forensic_quant import forensic_agent
from backend.agents.contract_catalyst import contract_agent
from backend.agents.flow_gamma import flow_agent
from backend.agents.cio_risk import cio_agent
from backend.agents.learning_agent import learning_agent
from backend.agents.web_intel_agent import web_intel_agent
from backend.agents.boss_agent import boss_agent
from backend.agents.momentum_agent import momentum_agent
from backend.agents.mean_reversion_agent import mean_reversion_agent
from backend.agents.earnings_agent import earnings_agent
from backend.agents.analyst_agent import analyst_agent
from backend.agents.sector_rotation_agent import sector_rotation_agent
from backend.agents.regime_agent import regime_agent
from backend.agents.hedging_agent import hedging_agent
from backend.execution.paper_engine import paper_engine
from backend.notifications.telegram import telegram_notifier

# Register all core agents in central dynamic registry
agent_registry.register(sec_agent)
agent_registry.register(forensic_agent)
agent_registry.register(contract_agent)
agent_registry.register(flow_agent)
agent_registry.register(cio_agent)
agent_registry.register(learning_agent)
agent_registry.register(web_intel_agent)
agent_registry.register(boss_agent)
agent_registry.register(regime_agent)
agent_registry.register(momentum_agent)
agent_registry.register(mean_reversion_agent)
agent_registry.register(earnings_agent)
agent_registry.register(analyst_agent)
agent_registry.register(sector_rotation_agent)
agent_registry.register(hedging_agent)

# Ensure data directory exists
os.makedirs(os.path.dirname(settings.LOG_FILE_PATH), exist_ok=True)

# Comprehensive Logging Configuration
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    settings.LOG_FILE_PATH,
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8"
)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

logger = logging.getLogger("alphaforge")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing AlphaForge Multi-Agent Engine & Audit Logger...")
    await init_db()
    await paper_engine.record_snapshot()
    
    is_testing = os.environ.get("TESTING") == "true"
    if not is_testing:
        logger.info("Launching agents and Telegram bot...")
        await agent_registry.start_all()
        await telegram_notifier.start_polling()
        logger.info("AlphaForge agents running; listening for Telegram commands.")
        if telegram_notifier.is_configured:
            account = await paper_engine.get_account_summary()
            asyncio.create_task(telegram_notifier.send_message(
                "🚀 <b>ALPHAFORGE ONLINE</b>\n\n"
                f"• <b>Agents:</b> {len(agent_registry.list_agents())}\n"
                f"• <b>Equity:</b> ${account['total_equity']:.2f} (paper)\n\n"
                "<i>Send /boss, /status, or /portfolio anytime.</i>"
            ))
        
    yield
    
    if not is_testing:
        logger.info("Shutting down agent swarm and Telegram listener...")
        await agent_registry.stop_all()
        await telegram_notifier.stop_polling()
        logger.info("All agents stopped safely.")

app = FastAPI(
    title="AlphaForge Quant & Multi-Agent Trading Engine",
    description="Autonomous institutional-grade trading intelligence running on free public data feeds.",
    version="1.2.0",
    lifespan=lifespan
)

# The dashboard is served from this same origin, so no cross-origin access is needed.
app.middleware("http")(auth_middleware)
app.include_router(auth_router)

# WebSocket live stream endpoint
@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    if not websocket_authorized(websocket):
        await websocket.close(code=1008)
        return
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)

# Include API routes
app.include_router(api_router)

# Mount Static Files (Production UI)
static_dir = os.path.join(BASE_DIR, "backend", "static")
os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        target_file = os.path.join(static_dir, full_path)
        if full_path and os.path.exists(target_file) and not os.path.isdir(target_file):
            return FileResponse(target_file)
        return FileResponse(index_file)
    return {"message": "AlphaForge API Running. Frontend is compiling...", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)
