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


def test_watch_step():
    from datetime import date

    from aucs_api.services.me import watch_step

    today = date(2026, 10, 19)
    assert watch_step(None, date(2026, 10, 25), today) == "review"
    assert watch_step("money", date(2026, 10, 25), today) == "money"
    assert watch_step("money", date(2026, 10, 18), today) == "result"
    assert watch_step("odd", None, today) == "review"
