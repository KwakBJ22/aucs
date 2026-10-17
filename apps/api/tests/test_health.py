from aucs_api import settings
from aucs_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_ok() -> None:
    assert client.get("/health").json() == {"ok": True}


def test_health_db_without_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL", "")
    body = client.get("/health/db").json()
    assert body["ok"] is False
    assert "postgres" not in str(body)
