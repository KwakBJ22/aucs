from aucs_workers.collectors import court_docs as m


class _P:
    def __init__(self) -> None:
        self.what: list[str] = []

    def call(self, fn, what):  # type: ignore[no-untyped-def]
        self.what.append(what.split(" ", 1)[1])
        return {"ok": True, "data": {"x": 1}}


def test_archive_skips_status_when_already_have() -> None:
    # 11/24: 현황조사서는 한 번 쓰면 거의 안 바뀜 → 이미 받은 사건은 문건송달만
    p = _P()
    out = m.fetch_case(None, p, "B000250", "2025타경1", docs_only=True, has_status=True)  # type: ignore[arg-type]
    assert p.what == ["문건송달"] and "status_report" not in out
    p = _P()
    m.fetch_case(None, p, "B000250", "2025타경1", docs_only=True)  # type: ignore[arg-type]
    assert p.what == ["문건송달", "현황조사"]


def test_new_case_gets_status_with_details(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(m, "_details", lambda post, court, cs, seqs, out: None)
    p = _P()
    out = m.fetch_case(None, p, "B000250", "2025타경1", [1], False, with_status=True)  # type: ignore[arg-type]
    assert p.what == ["현황조사"] and out["status_report"]
    p = _P()
    m.fetch_case(None, p, "B000250", "2025타경1", [1], False)  # type: ignore[arg-type]
    assert p.what == []
