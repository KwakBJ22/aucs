"""화면 한 번에 부르기(11/3): 홈 공개 자료·내 경매·내 정보 묶음 주소가 각 자료를 다 담는지."""

from aucs_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_home_feed_bundles_lists_market_notices(monkeypatch) -> None:
    from aucs_api.services import admin_ops, items, picks, pro

    calls: list[str] = []

    def fake_list(**k):
        calls.append(k.get("source", "all"))
        return {"total": 1, "items": [{"item_id": k.get("source", "all")}]}

    monkeypatch.setattr(items, "list_items", fake_list)
    monkeypatch.setattr(pro, "market", lambda f, today: {"courts": []})
    monkeypatch.setattr(admin_ops, "notices", lambda active_only: [{"title": "공지"}])
    monkeypatch.setattr(picks, "home_picks", lambda **k: {"picks": [], "soon": [], "next": []})
    r = client.get("/home-feed?sigungu=강남구&market=true").json()
    assert sorted(calls) == ["all", "onbid"]
    assert (
        r["mine"]["items"][0]["item_id"] == "all"
        and r["onbid_soon"]["items"][0]["item_id"] == "onbid"
    )
    assert r["market"] == {"courts": []} and r["notices"][0]["title"] == "공지"


def test_me_auction_and_more(monkeypatch) -> None:
    from aucs_api.auth.user import current_user_id
    from aucs_api.routers import me as me_router
    from aucs_api.services import admin_ops, me, mock

    app.dependency_overrides[current_user_id] = lambda: "u1"
    monkeypatch.setattr(me_router, "current_user_id", lambda authorization: "u1")
    monkeypatch.setattr(admin_ops, "is_limited", lambda uid: False)
    monkeypatch.setattr(me, "watch_list", lambda uid, today: [1])
    monkeypatch.setattr(me, "bids", lambda uid, today: {"todo": []})
    monkeypatch.setattr(mock, "listing", lambda uid, today: [2])
    monkeypatch.setattr(me, "searches", lambda uid: [3])
    monkeypatch.setattr(admin_ops, "my_inquiries", lambda uid: [4])
    try:
        h = {"Authorization": "Bearer x"}
        assert client.get("/me/auction", headers=h).json() == {
            "watch": [1],
            "bids": {"todo": []},
            "mocks": [2],
        }
        assert client.get("/me/more", headers=h).json() == {"searches": [3], "inquiries": [4]}
    finally:
        app.dependency_overrides.clear()
