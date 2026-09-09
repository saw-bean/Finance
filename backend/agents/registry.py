import asyncio
import logging
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.agents.base import BaseAgent
from backend.api.websocket import ws_manager

logger = logging.getLogger("alphaforge.registry")

class AgentRegistry:
    """
    Central Dynamic Agent Registry & Swarm Lifecycle Controller.
    Supports runtime registration, dynamic agent compilation/spawning, 
    individual agent pause/resume, and safe hot-reloading.
    """
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._is_running: bool = False

    def register(self, agent: BaseAgent):
        """Registers a BaseAgent instance in the swarm."""
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} ({agent.display_name})")

    def unregister(self, name: str) -> Optional[BaseAgent]:
        """Unregisters an agent by name."""
        return self._agents.pop(name, None)

    def get(self, name: str) -> Optional[BaseAgent]:
        """Retrieves an agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> List[BaseAgent]:
        """Returns a list of all currently registered agents."""
        return list(self._agents.values())

    async def load_custom_agents(self):
        """Discovers and instantiates any custom agent .py files in backend/agents/custom/ on startup."""
        custom_dir = Path(__file__).resolve().parent / "custom"
        if not custom_dir.exists():
            return
            
        for file_path in custom_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
            try:
                module_name = f"backend.agents.custom.{file_path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, str(file_path))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BaseAgent) and attr is not BaseAgent:
                            inst = attr()
                            if inst.name not in self._agents:
                                self.register(inst)
                                logger.info(f"Auto-loaded custom agent on startup: {inst.name} ({inst.display_name})")
            except Exception as e:
                logger.error(f"Error auto-loading custom agent from {file_path.name}: {e}")

    async def start_all(self):
        """Loads all custom agents and starts background execution loops for all registered agents."""
        await self.load_custom_agents()
        self._is_running = True
        logger.info(f"Starting all {len(self._agents)} swarm agents...")
        for name, agent in self._agents.items():
            try:
                await agent.start()
            except Exception as e:
                logger.error(f"Error starting agent {name}: {e}", exc_info=True)

    async def stop_all(self):
        """Gracefully stops all agents."""
        self._is_running = False
        logger.info("Stopping all swarm agents...")
        for name, agent in self._agents.items():
            try:
                await agent.stop()
            except Exception as e:
                logger.error(f"Error stopping agent {name}: {e}")

    async def spawn_dynamic_agent_from_file(
        self,
        file_path: Path,
        class_name: str,
        name: str,
        display_name: str,
        interval_seconds: int = 60
    ) -> BaseAgent:
        """
        Dynamically loads, instantiates, and boots an agent from a validated Python file.
        """
        module_name = f"backend.agents.custom.{file_path.stem}"
        
        # Load module dynamically
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module specification from {file_path}")
            
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # Get class
        if not hasattr(module, class_name):
            raise AttributeError(f"Module {module_name} does not have class '{class_name}'")
            
        agent_cls = getattr(module, class_name)
        if not issubclass(agent_cls, BaseAgent):
            raise TypeError(f"Class '{class_name}' must inherit from BaseAgent")
            
        # Instantiate
        agent_instance = agent_cls()
        
        # Stop existing instance if replacing
        if name in self._agents:
            old_agent = self._agents[name]
            await old_agent.stop()
            
        self.register(agent_instance)
        
        # If swarm is active, launch immediately
        if self._is_running:
            await agent_instance.start()
            
        logger.info(f"✨ Dynamically spawned and launched custom agent: {name} ({display_name})")
        
        await ws_manager.broadcast("DYNAMIC_AGENT_SPAWNED", {
            "name": name,
            "display_name": display_name,
            "interval_seconds": interval_seconds,
            "class_name": class_name,
            "file_path": str(file_path)
        })
        
        return agent_instance

    async def pause_agent(self, name: str) -> bool:
        """Pauses a single agent without stopping the swarm."""
        agent = self.get(name)
        if agent and agent.running:
            await agent.stop()
            await agent.update_status("PAUSED")
            return True
        return False

    async def resume_agent(self, name: str) -> bool:
        """Resumes a paused agent."""
        agent = self.get(name)
        if agent and not agent.running:
            await agent.start()
            return True
        return False

# Global Registry Singleton
agent_registry = AgentRegistry()
