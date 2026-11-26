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
    assert not m.nationwide_due(datetime(2026, 11, 23, 14, 10))  # 11/26 밤부터 멈춤
    monkeypatch.setattr(m, "NATIONWIDE_ON", True)
    assert not m.nationwide_due(datetime(2026, 11, 23, 13, 10))
    assert m.nationwide_due(datetime(2026, 11, 23, 14, 10))
    (tmp_path / "done").write_text("2026-11-23", encoding="utf-8")
    assert not m.nationwide_due(datetime(2026, 11, 23, 16, 10))
    assert m.nationwide_due(datetime(2026, 11, 24, 14, 10))


def test_official_prices_once_a_day_from_15(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from datetime import datetime

    monkeypatch.setattr(m, "OFFICIAL_DONE", tmp_path / "done")
    assert not m.official_due(datetime(2026, 11, 25, 14, 10))
    assert m.official_due(datetime(2026, 11, 25, 16, 10))
    (tmp_path / "done").write_text("2026-11-25", encoding="utf-8")
    assert not m.official_due(datetime(2026, 11, 25, 17, 10))


def test_docs_pc_runs_only_archive(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 11/26: 2번 PC(AUCS_ROLE=docs)는 서류 보관만, 1번 PC 는 2번 PC 가 살아 있으면 서류 보관을 건너뜀
    calls: list[list[str]] = []
    monkeypatch.setattr(m, "LOCK", tmp_path / "lock")
    monkeypatch.setattr(m, "NATIONWIDE_DONE", tmp_path / "nw")
    monkeypatch.setattr(m, "OFFICIAL_DONE", tmp_path / "of")
    monkeypatch.setattr(m, "SERVICE", range(0, 24))
    monkeypatch.setattr(m, "heartbeat", lambda: None)
    monkeypatch.setattr(m, "nationwide_due", lambda now: False)
    monkeypatch.setattr(m, "official_due", lambda now: False)
    monkeypatch.setattr(m, "_cap", lambda: 1800)
    monkeypatch.setattr(m.subprocess, "call", lambda cmd, **kw: calls.append(cmd) or 0)
    monkeypatch.setenv("AUCS_ROLE", "docs")
    m.main()
    # 11/26 밤: 2번 PC 는 명세서 원본 → 서류 보관
    assert [c[-1] for c in calls] == ["aucs_workers.collectors.court_spec", "--archive"]
    calls.clear()
    monkeypatch.setenv("AUCS_ROLE", "main")
    monkeypatch.setattr(m, "docs_pc_alive", lambda: True)
    for f in ("_new_left", "_soon_left", "_details_left"):
        monkeypatch.setattr(m, f, lambda: True)
    m.main()
    assert "--archive" not in [c[-1] for c in calls] and "--new" in [c[-1] for c in calls]
