import asyncio
import logging
from typing import Dict, Any, List, Optional
from backend.agents.base import BaseAgent

logger = logging.getLogger("alphaforge.registry")

class AgentRegistry:
    """
    Central Dynamic Agent Registry & Swarm Lifecycle Controller.
    Supports registration and individual agent pause/resume.
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

    async def start_all(self):
        """Starts background execution loops for all registered agents."""
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
