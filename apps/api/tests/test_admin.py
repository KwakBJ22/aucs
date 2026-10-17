from aucs_api import settings
from aucs_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_admin_needs_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "")
    assert client.get("/admin/status").status_code == 403
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "abc")
    assert client.get("/admin/status", headers={"X-Admin-Token": "wrong"}).status_code == 403


def test_admin_flags_unknown_key(monkeypatch) -> None:
    from aucs_api.services import admin

    monkeypatch.setattr(settings, "ADMIN_TOKEN", "abc")
    monkeypatch.setattr(admin, "set_flag", lambda k, e: None)
    r = client.put("/admin/flags/nope", json={"enabled": True}, headers={"X-Admin-Token": "abc"})
    assert r.status_code == 404
