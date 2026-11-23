import os
import time

from aucs_workers.jobs import court_hourly as m


def test_dead_lock_does_not_block(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 11/22: 09:10 차례가 끊긴 뒤 남은 잠금 때문에 10:10 차례가 건너뜀
    lock = tmp_path / "court_hourly.lock"
    monkeypatch.setattr(m, "LOCK", lock)
    assert not m.busy()
    lock.write_text(str(os.getpid()), encoding="utf-8")
    assert m.busy()  # 살아 있는 프로세스 → 기다림
    monkeypatch.setattr(m, "alive", lambda pid: False)
    assert not m.busy()  # 이미 끝난 프로세스 → 바로 돎
    monkeypatch.setattr(m, "alive", lambda pid: True)
    old = time.time() - 71 * 60
    os.utime(lock, (old, old))
    assert not m.busy()  # 70분 지나면 예전처럼 돎


def test_alive() -> None:
    assert m.alive(os.getpid()) and not m.alive(0)


def test_nationwide_once_a_day_from_14(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from datetime import datetime

    monkeypatch.setattr(m, "NATIONWIDE_DONE", tmp_path / "done")
    assert not m.nationwide_due(datetime(2026, 11, 23, 13, 10))
    assert m.nationwide_due(datetime(2026, 11, 23, 14, 10))
    (tmp_path / "done").write_text("2026-11-23", encoding="utf-8")
    assert not m.nationwide_due(datetime(2026, 11, 23, 16, 10))
    assert m.nationwide_due(datetime(2026, 11, 24, 14, 10))
