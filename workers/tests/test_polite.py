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
    a, b = Polite(sleep=lambda s: None, jitter=False), Polite(sleep=lambda s: None, jitter=False)
    a.call(lambda: {"ok": True}, "1")
    b.call(lambda: {"ok": True}, "2")
    with pytest.raises(DailyLimitReached):
        a.call(lambda: {"ok": True}, "3")
