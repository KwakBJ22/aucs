import pytest
from aucs_workers.collectors.polite import Blocked, DailyLimitReached, Polite


def test_stops_after_three_bad_answers() -> None:
    calls = []
    p = Polite(sleep=lambda s: None, site=None, jitter=False)
    with pytest.raises(Blocked):
        p.call(lambda: calls.append(1) or {"ok": False, "status": 403}, "시험")
    assert len(calls) == 3


def test_daily_limit() -> None:
    p = Polite(daily_limit=1, sleep=lambda s: None, site=None, jitter=False)
    p.call(lambda: {"ok": True}, "1")
    with pytest.raises(DailyLimitReached):
        p.call(lambda: {"ok": True}, "2")


def test_block_marker_stops_next_run(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 막히면 표시를 남기고, 다음 수집기는 켜자마자 멈춤(11/4 법원 「비정상 IP」)
    from aucs_workers.collectors import polite as m

    monkeypatch.setattr(m, "LOGS", tmp_path)
    p = Polite(sleep=lambda s: None, jitter=False)
    with pytest.raises(Blocked):
        p.call(lambda: {"ok": False, "msg": "비정상 IP 입니다"}, "시험")
    assert p.count == 1  # 「비정상」은 다시 시도하지 않음
    with pytest.raises(Blocked):
        Polite(sleep=lambda s: None)


def test_site_budget_shared(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from aucs_workers.collectors import polite as m

    monkeypatch.setattr(m, "LOGS", tmp_path)
    monkeypatch.setitem(m.SITE_DAY_MAX, "court", 2)
    a = Polite(sleep=lambda s: None, jitter=False, hourly=False)
    b = Polite(sleep=lambda s: None, jitter=False, hourly=False)
    a.call(lambda: {"ok": True}, "1")
    b.call(lambda: {"ok": True}, "2")
    with pytest.raises(DailyLimitReached):
        a.call(lambda: {"ok": True}, "3")


def test_budget_grows_after_quiet_days_and_shrinks_on_block() -> None:
    # 2,500번은 시작점 — 3일 무사하면 20% 올리고(11/18, 처음엔 7일), 막히면 40% 내림
    from aucs_workers.collectors.polite import hour_share, roll

    b: dict = {}
    for d in range(1, 5):
        b = roll(b, f"2026-11-{d:02d}", 2500)
    assert b["cap"] == 3000 and b["ok_days"] == 0
    b["blocked"] = True
    assert roll(b, "2026-11-09", 2500)["ok_days"] == 0
    assert hour_share(2500) == 139


def test_budget_ignores_older_clock() -> None:
    # 11/18: 시계가 하루 늦은 곳이 읽어도 셈 · 한도 · 무사한 날을 건드리지 않음(날짜가 엇갈려 20,000 까지 오른 사고)
    from aucs_workers.collectors.polite import roll

    b = {"date": "2026-11-18", "count": 140, "hours": {"06": 140}, "cap": 3000, "ok_days": 6}
    for _ in range(10):
        b = roll(b, "2026-11-17", 2500)
        b = roll(b, "2026-11-18", 2500)
    assert (
        b["date"] == "2026-11-18" and b["count"] == 140 and b["cap"] == 3000 and b["ok_days"] == 6
    )
    nxt = roll(b, "2026-11-19", 2500)
    assert nxt["cap"] == 3600 and nxt["count"] == 0


def test_hour_share_stops_hourly_job(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from aucs_workers.collectors import polite as m

    monkeypatch.setattr(m, "LOGS", tmp_path)
    monkeypatch.setattr(m, "REQUEST_GAP_SEC", 0)
    monkeypatch.setitem(m.SITE_DAY_MAX, "court", 18)  # 시간 몫 1번
    p = Polite(sleep=lambda s: None, jitter=False)
    p.call(lambda: {"ok": True}, "1")
    with pytest.raises(DailyLimitReached):
        p.call(lambda: {"ok": True}, "2")
    Polite(sleep=lambda s: None, jitter=False, hourly=False).call(lambda: {"ok": True}, "목록")


def test_pause_hours_grow_within_day() -> None:
    # 막히면 1시간, 같은 날 또 막히면 2·4시간(11/4 저녁 — 12시간은 지나쳤음)
    from aucs_workers.collectors.polite import pause_hours

    assert [pause_hours(n) for n in (1, 2, 3, 4)] == [2, 4, 4, 4]


def test_step_share_from_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 매시 작업이 단계마다 몫을 나눠 줌 — 앞 단계가 시간 몫을 다 쓰지 않게(11/5)
    monkeypatch.setenv("AUCS_STEP_REQ", "1")
    p = Polite(sleep=lambda s: None, site=None, jitter=False)
    p.call(lambda: {"ok": True}, "1")
    with pytest.raises(DailyLimitReached):
        p.call(lambda: {"ok": True}, "2")


def test_long_block_asks_once_a_day(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 11/9 오래 막힘: 「until」 전에는 아예 묻지 않고, 지난 뒤 1번 물어 또 막히면 24시간 뒤로
    from datetime import timedelta

    from aucs_workers.collectors import polite as m

    now = m.now_kst

    monkeypatch.setattr(m, "LOGS", tmp_path)
    f = tmp_path / "court_blocked.txt"
    f.write_text(f"x\nuntil {now() + timedelta(hours=3):%Y-%m-%d %H:%M}\n", encoding="utf-8")
    with pytest.raises(Blocked):
        Polite(sleep=lambda s: None)
    f.write_text(f"x\nuntil {now() - timedelta(minutes=1):%Y-%m-%d %H:%M}\n", encoding="utf-8")
    p = Polite(sleep=lambda s: None, jitter=False)  # 확인 차례 — 열림
    with pytest.raises(Blocked):
        p.call(lambda: {"ok": False, "msg": "비정상 IP"}, "확인")
    assert p.count == 1
    nxt = m.read_until(f.read_text(encoding="utf-8"))
    assert nxt is not None and nxt > now() + timedelta(hours=23)


def test_hour_key_is_korea_time(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 11/21: 관리자 요청으로 돈 수집이 장부에 세계 표준시 시각(03시)으로 적혔음 → 늘 한국 시각
    import json
    from datetime import datetime, timedelta, timezone

    from aucs_workers.collectors import polite as m

    monkeypatch.setattr(m, "LOGS", tmp_path)
    monkeypatch.setattr(m, "REQUEST_GAP_SEC", 0)
    Polite(sleep=lambda s: None, jitter=False, hourly=False).call(lambda: {"ok": True}, "1")
    b = json.loads((tmp_path / "court_budget.json").read_text(encoding="utf-8"))
    k = datetime.now(timezone(timedelta(hours=9)))
    assert b["date"] == k.date().isoformat() and list(b["hours"]) == [f"{k:%H}"]


def test_hour_max_all_waits_next_hour(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 11/23: 몫 없이 도는 수집(아침 묶음 · 전국 보관)도 한 시간 861번(11/22 07시)을 넘지 않게 기다림
    import json

    from aucs_workers.collectors import polite as m

    monkeypatch.setattr(m, "LOGS", tmp_path)
    monkeypatch.setattr(m, "REQUEST_GAP_SEC", 0)
    monkeypatch.setattr(m, "HOUR_MAX_ALL", 1)
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        if s > 60:  # 다음 시간이 된 것처럼
            f = tmp_path / "court_budget.json"
            b = json.loads(f.read_text(encoding="utf-8"))
            b["hours"] = {}
            f.write_text(json.dumps(b), encoding="utf-8")

    p = Polite(sleep=sleep, jitter=False, hourly=False)
    p.call(lambda: {"ok": True}, "1")
    p.call(lambda: {"ok": True}, "2")
    assert any(s > 60 for s in slept)
    b = json.loads((tmp_path / "court_budget.json").read_text(encoding="utf-8"))
    assert sum(b["by"].values()) == 2


def test_history_kept_when_day_changes(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import json

    from aucs_workers.collectors import polite as m

    monkeypatch.setattr(m, "LOGS", tmp_path)
    old = {"date": "2026-11-22", "count": 9, "hours": {"07": 9}, "cap": 8640, "ok_days": 1}
    (tmp_path / "court_budget.json").write_text(json.dumps(old), encoding="utf-8")
    Polite(sleep=lambda s: None, jitter=False)._load()
    lines = (tmp_path / "court_budget_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["date"] == "2026-11-22"
