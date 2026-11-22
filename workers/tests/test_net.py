import httpx
import pytest
from aucs_workers.collectors.net import get_retry


def _client(fails: int) -> tuple[httpx.Client, list[int]]:
    calls: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) <= fails:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        return httpx.Response(200, text="{}")

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_retries_disconnect_then_ok() -> None:
    # 11/22 아침 브이월드가 연결을 끊어 공시가격 · 토지이용계획 단계가 통째로 실패했던 것
    c, calls = _client(2)
    waits: list[float] = []
    assert get_retry(c, "https://x/y", sleep=waits.append).status_code == 200
    assert len(calls) == 3 and waits == [60.0, 120.0]


def test_gives_up_after_three() -> None:
    c, calls = _client(5)
    with pytest.raises(httpx.RemoteProtocolError):
        get_retry(c, "https://x/y", sleep=lambda s: None)
    assert len(calls) == 3


def test_nationwide_retries_failed_to_fetch_only() -> None:
    from aucs_workers.collectors.court_nationwide import call_retry
    from aucs_workers.collectors.polite import Polite

    p = Polite(sleep=lambda s: None, site=None, jitter=False)
    n: list[int] = []

    def flaky() -> dict:
        n.append(1)
        if len(n) == 1:
            raise RuntimeError("Page.evaluate: TypeError: Failed to fetch")
        return {"ok": True, "rows": []}

    assert call_retry(p, flaky, "시험", sleep=lambda s: None)["ok"] and len(n) == 2
    with pytest.raises(ValueError):
        call_retry(
            p, lambda: (_ for _ in ()).throw(ValueError("다른 오류")), "시험", sleep=lambda s: None
        )
