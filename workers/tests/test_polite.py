import pytest
from aucs_workers.collectors.polite import Blocked, DailyLimitReached, Polite


def test_stops_after_three_bad_answers() -> None:
    calls = []
    p = Polite(sleep=lambda s: None)
    with pytest.raises(Blocked):
        p.call(lambda: calls.append(1) or {"ok": False, "status": 403}, "시험")
    assert len(calls) == 3


def test_daily_limit() -> None:
    p = Polite(daily_limit=1, sleep=lambda s: None)
    p.call(lambda: {"ok": True}, "1")
    with pytest.raises(DailyLimitReached):
        p.call(lambda: {"ok": True}, "2")
