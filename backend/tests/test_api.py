import pytest
from starlette.testclient import TestClient
from backend.main import app
from backend.db.session import init_db

@pytest.mark.asyncio
async def test_api_status_and_routes():
    await init_db()
    with TestClient(app) as client:
        res = client.get("/api/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ONLINE"
        assert "account" in data
        assert "active_agents" in data

        sig_res = client.get("/api/signals")
        assert sig_res.status_code == 200
        assert isinstance(sig_res.json(), list)

        port_res = client.get("/api/portfolio")
        assert port_res.status_code == 200
        assert "summary" in port_res.json()

        settings_res = client.get("/api/settings")
        assert settings_res.status_code == 200
        assert "SEC_USER_AGENT" in settings_res.json()
