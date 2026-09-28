import datetime
from starlette.testclient import TestClient

from backend.main import app
from backend.config import settings
from backend.agents.cio_risk import is_market_open


def test_api_requires_token_when_configured(monkeypatch):
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setattr(settings, "API_TOKEN", "s3cret-token")
    client = TestClient(app)

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/portfolio").status_code == 401
    assert client.get("/api/portfolio", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"

    login = client.post("/login", data={"token": "s3cret-token"}, follow_redirects=False)
    assert login.status_code == 303
    assert client.get("/api/settings").status_code == 200  # cookie now set

    assert TestClient(app).post("/login", data={"token": "nope"}).status_code == 401


def test_market_hours():
    ny = datetime.timezone(datetime.timedelta(hours=-4))  # EDT
    assert is_market_open(datetime.datetime(2026, 9, 28, 10, 0, tzinfo=ny))      # Monday 10:00
    assert not is_market_open(datetime.datetime(2026, 9, 28, 9, 29, tzinfo=ny))  # before open
    assert not is_market_open(datetime.datetime(2026, 9, 28, 16, 0, tzinfo=ny))  # at close
    assert not is_market_open(datetime.datetime(2026, 9, 27, 12, 0, tzinfo=ny))  # Sunday
