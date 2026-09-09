import pytest
import os
import asyncio
from pathlib import Path

os.environ["TESTING"] = "true"

from backend.db.session import init_db
from backend.agents.boss_coder import boss_coder, BossCoder
from backend.agents.registry import agent_registry
from backend.agents.boss_agent import boss_agent

@pytest.mark.asyncio
async def test_boss_coder_ast_validation():
    # 1. Valid code inheriting from BaseAgent
    valid_code = """
import logging
from backend.agents.base import BaseAgent

class MockStrategyAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="mock_agent", display_name="Mock Strategy Agent", interval_seconds=30)

    async def run_iteration(self):
        pass
"""
    is_valid, msg = BossCoder.validate_code_ast(valid_code, expected_class="MockStrategyAgent")
    assert is_valid, f"Expected valid AST, got error: {msg}"

    # 2. Syntax error code
    invalid_syntax = """
def broken_syntax(
    return "missing close"
"""
    is_valid, msg = BossCoder.validate_code_ast(invalid_syntax)
    assert not is_valid
    assert "SyntaxError" in msg

    # 3. Security check: forbidden system call
    forbidden_code = """
import os
from backend.agents.base import BaseAgent

class MaliciousAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="bad_agent", display_name="Bad Agent")
        os.system("echo dangerous")

    async def run_iteration(self):
        pass
"""
    is_valid, msg = BossCoder.validate_code_ast(forbidden_code, expected_class="MaliciousAgent")
    assert not is_valid
    assert "Security Violation" in msg

@pytest.mark.asyncio
async def test_boss_coder_sandbox_verification():
    valid_code = """
import asyncio
import logging
from backend.agents.base import BaseAgent

class SandboxTestAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="sandbox_test_agent", display_name="Sandbox Test Agent", interval_seconds=45)

    async def run_iteration(self):
        await self.log("INFO", "Running sandbox iteration...")
"""
    passed, msg, stats = await BossCoder.sandbox_verify(valid_code, class_name="SandboxTestAgent")
    assert passed, f"Sandbox test failed: {msg}"
    assert stats["agent_name"] == "sandbox_test_agent"
    assert stats["interval_seconds"] == 45

@pytest.mark.asyncio
async def test_strategy_generation_and_spawning():
    await init_db()
    
    # 1. Test strategy generation for Biotech FDA
    code, class_name, file_name = boss_coder.generate_strategy_code("BIOTECH_FDA")
    assert "BiotechFdaCatalystAgent" in class_name
    assert "biotech_fda_catalyst.py" in file_name
    
    # 2. Test spawning and dynamic deployment
    success, msg, agent_inst = await boss_agent.synthesize_and_deploy_agent(
        strategy_type="BIOTECH_FDA"
    )
    assert success, f"Failed to synthesize and deploy: {msg}"
    assert agent_inst is not None
    assert agent_inst.name == "biotech_fda_agent"
    
    # Verify registered in central agent registry
    retrieved = agent_registry.get("biotech_fda_agent")
    assert retrieved is not None
    assert retrieved.display_name == "Biotech & FDA PDUFA Catalyst Sniper"

@pytest.mark.asyncio
async def test_boss_system_audit():
    await init_db()
    audit = await boss_agent.conduct_system_audit()
    
    assert "health_score" in audit
    assert 0 <= audit["health_score"] <= 100
    assert "account" in audit
    assert "agent_performance" in audit
    assert "recommendations" in audit
    assert len(audit["agent_performance"]) > 0

@pytest.mark.asyncio
async def test_boss_api_endpoints():
    import httpx
    from backend.main import app
    
    await init_db()
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Audit endpoint
        res = await client.get("/api/boss/audit")
        assert res.status_code == 200
        data = res.json()
        assert "health_score" in data
        assert "account" in data

        # 2. Spawn endpoint
        res = await client.post("/api/boss/spawn", json={"strategy_type": "CRYPTO_MACRO"})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True

        # 3. Evolutions endpoint
        res = await client.get("/api/boss/evolutions")
        assert res.status_code == 200
        evos = res.json()
        assert len(evos) > 0

        # 4. Directives endpoint
        res = await client.post("/api/boss/tune", json={
            "directive_key": "TEST_KEY",
            "value": {"threshold": 0.85},
            "description": "Test directive"
        })
        assert res.status_code == 200
        
        res = await client.get("/api/boss/directives")
        assert res.status_code == 200
        dirs = res.json()
        assert any(d["directive_key"] == "TEST_KEY" for d in dirs)

