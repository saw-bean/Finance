import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings, BASE_DIR
from backend.db.session import init_db
from backend.api.routes import router as api_router
from backend.api.websocket import ws_manager

# Import Autonomous Swarm Agents & Registry
from backend.agents.registry import agent_registry
from backend.agents.sec_edgar import sec_agent
from backend.agents.forensic_quant import forensic_agent
from backend.agents.contract_catalyst import contract_agent
from backend.agents.flow_gamma import flow_agent
from backend.agents.cio_risk import cio_agent
from backend.agents.learning_agent import learning_agent
from backend.agents.web_intel_agent import web_intel_agent
from backend.agents.evolution_agent import evolution_agent
from backend.agents.boss_agent import boss_agent
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
agent_registry.register(evolution_agent)
agent_registry.register(boss_agent)

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
        logger.info("Launching autonomous 9-agent swarm with Boss Director & Telegram bot...")
        await agent_registry.start_all()
        await telegram_notifier.start_polling()
        logger.info("AlphaForge Swarm is active, governed by Boss Architect, listening for Telegram commands.")
        if telegram_notifier.is_configured:
            asyncio.create_task(telegram_notifier.send_message(
                "🚀 <b>ALPHAFORGE 24/7 MULTI-AGENT SWARM ACTIVE</b>\n\n"
                "• <b>Status:</b> Online & Trading 24/7\n"
                "• <b>Swarm:</b> 9 Autonomous Agents (Governed by Boss Director)\n"
                "• <b>Capital:</b> $100.00\n"
                "• <b>Alerts:</b> Telegram Push Enabled\n\n"
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket live stream endpoint
@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
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
