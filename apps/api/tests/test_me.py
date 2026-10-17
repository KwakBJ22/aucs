from aucs_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_me_needs_login() -> None:
    assert client.get("/me/watch").status_code == 401
    assert client.put("/me/watch/x", headers={"Authorization": "Bearer "}).status_code == 401


def test_me_with_fake_user() -> None:
    from aucs_api.auth.user import current_user_id
    from aucs_api.services import me

    app.dependency_overrides[current_user_id] = lambda: "u1"
    me_calls = []
    orig = me.watch_add
    me.watch_add = lambda uid, item: me_calls.append((uid, item))  # type: ignore[assignment]
    try:
        assert client.put("/me/watch/B000250-2025타경55580-1").json() == {"ok": True}
        assert me_calls == [("u1", "B000250-2025타경55580-1")]
    finally:
        me.watch_add = orig  # type: ignore[assignment]
        app.dependency_overrides.clear()
