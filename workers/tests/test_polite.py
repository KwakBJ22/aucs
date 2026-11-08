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


def test_budget_grows_after_quiet_week_and_shrinks_on_block() -> None:
    # 2,500번은 시작점 — 7일 무사하면 20% 올리고(11/4 저녁), 막히면 40% 내림
    from aucs_workers.collectors.polite import hour_share, roll

    b: dict = {}
    for d in range(1, 9):
        b = roll(b, f"2026-11-{d:02d}", 2500)
    assert b["cap"] == 3000 and b["ok_days"] == 0
    b["blocked"] = True
    assert roll(b, "2026-11-09", 2500)["ok_days"] == 0
    assert hour_share(2500) == 139


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

    assert [pause_hours(n) for n in (1, 2, 3, 4)] == [1, 2, 4, 4]


def test_step_share_from_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 매시 작업이 단계마다 몫을 나눠 줌 — 앞 단계가 시간 몫을 다 쓰지 않게(11/5)
    monkeypatch.setenv("AUCS_STEP_REQ", "1")
    p = Polite(sleep=lambda s: None, site=None, jitter=False)
    p.call(lambda: {"ok": True}, "1")
    with pytest.raises(DailyLimitReached):
        p.call(lambda: {"ok": True}, "2")


def test_long_block_asks_once_a_day(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 11/9 오래 막힘: 「until」 전에는 아예 묻지 않고, 지난 뒤 1번 물어 또 막히면 24시간 뒤로
    from datetime import datetime, timedelta

    from aucs_workers.collectors import polite as m

    monkeypatch.setattr(m, "LOGS", tmp_path)
    f = tmp_path / "court_blocked.txt"
    f.write_text(
        f"x\nuntil {datetime.now() + timedelta(hours=3):%Y-%m-%d %H:%M}\n", encoding="utf-8"
    )
    with pytest.raises(Blocked):
        Polite(sleep=lambda s: None)
    f.write_text(
        f"x\nuntil {datetime.now() - timedelta(minutes=1):%Y-%m-%d %H:%M}\n", encoding="utf-8"
    )
    p = Polite(sleep=lambda s: None, jitter=False)  # 확인 차례 — 열림
    with pytest.raises(Blocked):
        p.call(lambda: {"ok": False, "msg": "비정상 IP"}, "확인")
    assert p.count == 1
    nxt = m.read_until(f.read_text(encoding="utf-8"))
    assert nxt is not None and nxt > datetime.now() + timedelta(hours=23)
