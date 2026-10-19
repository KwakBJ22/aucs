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
    assert watch_step(None, date(2026, 10, 25), today) == "found"
    assert watch_step("after", date(2026, 10, 18), today) == "after"
    assert watch_step("money", date(2026, 10, 25), today) == "money"
    assert watch_step("money", date(2026, 10, 18), today) == "result"
    assert watch_step("odd", None, today) == "found"


def test_history_rows():
    from datetime import datetime

    from aucs_api.services.me import history_rows

    at = datetime(2026, 10, 19, 9)
    rows = [
        {
            "kind": "min_price",
            "prev_value": "1015000000",
            "new_value": "710500000",
            "created_at": at,
        },
        {"kind": "sale_date", "prev_value": None, "new_value": "2026-10-20", "created_at": at},
        {"kind": "listing", "prev_value": "listed", "new_value": "gone", "created_at": at},
    ]
    h = history_rows(rows)
    assert h[0]["change"] == "10억 1,500만 → 7억 1,050만"
    assert len(h) == 2 and h[1]["change"] == "목록에 있음 → 빠짐"
