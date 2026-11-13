"""누구에게나 같은 공개 자료(물건 목록·상세·전문가 표·시장)는 잠깐 보관했다 바로 돌려줌.

자료는 하루 몇 번 모으므로 2분 보관이면 충분. 로그인 정보가 붙은 요청과 GET이 아닌 요청은 보관하지 않고,
관리자가 무엇을 바꾸면(/admin 의 GET 아닌 요청 성공) 보관한 것을 모두 비움.
"""

import functools
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, TypeVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

TTL = 120.0
MAX = 500
PREFIXES = ("/items", "/regions", "/pro/", "/home-feed", "/collections")
# 공개 자료를 바꾸는 건 관리자 요청뿐 — 관심·메모·사용 기록 같은 회원 요청으로는 비우지 않음(10/27)
CLEAR_ON = ("/admin",)

# 지역별 물건 수는 하루 한 번 바뀜 → 30분, 모아 보기는 분석(아침)마다 바뀜 → 10분.
# 홈 묶음도 10분(11/14) — 기억이 없을 때 한 번 받는 데 몇 초 걸려, 2분마다 누군가 그만큼 기다렸음
LONG = {"/regions": 1800.0, "/collections": 600.0, "/home-feed": 600.0}
# 보관 시간이 지나도 지난 값을 바로 주고 새 값은 뒤에서 받는 시간(11/4). 지역 수는 하루 한 번 바뀌므로 하루 —
# 첫 손님이 잠든 서버가 깨는 몇 초를 기다리지 않게. 나머지는 1분.
STALE = {"/regions": 86400, "/collections": 3600, "/home-feed": 3600}
_store: "OrderedDict[str, tuple[float, int, list[tuple[bytes, bytes]], bytes]]" = OrderedDict()
_memos: list[dict[Any, Any]] = []

F = TypeVar("F", bound=Callable[..., Any])


def memo(ttl: float = TTL, size: int = 300) -> Callable[[F], F]:
    """공개 자료 함수 결과를 잠깐 기억(같은 물건 상세를 비교함·상세·고른 물건이 다시 계산하지 않게, 10/27)."""

    def wrap(fn: F) -> F:
        box: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        lock = threading.Lock()
        _memos.append(box)

        @functools.wraps(fn)
        def inner(*a: Any, **k: Any) -> Any:
            key = (a, tuple(sorted(k.items())))
            hit = box.get(key)
            if hit and time.monotonic() - hit[0] < ttl:
                return hit[1]
            v = fn(*a, **k)
            with lock:
                box[key] = (time.monotonic(), v)
                box.move_to_end(key)
                while len(box) > size:
                    box.popitem(last=False)
            return v

        return inner  # type: ignore[return-value]

    return wrap


def clear() -> None:
    _store.clear()
    for b in _memos:
        b.clear()


def _cdn(path: str) -> tuple[bytes, bytes]:
    """공개 자료에 붙이는 보관 머리글: Vercel 앞단이 같은 시간만큼 보관했다 바로 돌려줌(브라우저는 보관 안 함)."""
    ttl = int(LONG.get(path, TTL))
    return (
        b"cache-control",
        f"public, max-age=0, s-maxage={ttl}, stale-while-revalidate={STALE.get(path, 60)}".encode(),
    )


class PublicCache:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method, path = scope["method"], scope["path"]
        headers = dict(scope.get("headers") or [])
        if method != "GET":
            status: list[int] = []

            async def watch(m: Message) -> None:
                if m["type"] == "http.response.start":
                    status.append(m["status"])
                await send(m)

            await self.app(scope, receive, watch)
            if status and status[0] < 400 and path.startswith(CLEAR_ON):
                clear()
            return
        if not path.startswith(PREFIXES) or b"authorization" in headers:
            await self.app(scope, receive, send)
            return
        key = path + "?" + scope.get("query_string", b"").decode()
        hit = _store.get(key)
        if hit and time.monotonic() - hit[0] < LONG.get(path, TTL):
            _, st, hd, body = hit
            await send({"type": "http.response.start", "status": st, "headers": [*hd, _cdn(path)]})
            await send({"type": "http.response.body", "body": body})
            return
        start: dict[str, Any] = {}
        parts: list[bytes] = []

        async def keep(m: Message) -> None:
            if m["type"] == "http.response.start":
                if m.get("status") == 200:  # Vercel 앞단(서울)도 같은 시간만큼 보관(11/3)
                    m = {**m, "headers": [*m.get("headers", []), _cdn(path)]}
                start.update(m)
            elif m["type"] == "http.response.body":
                parts.append(m.get("body", b""))
                if not m.get("more_body") and start.get("status") == 200:
                    hd = [
                        (k, v)
                        for k, v in start.get("headers", [])
                        if k.lower()
                        not in (b"access-control-allow-origin", b"vary", b"cache-control")
                    ]
                    _store[key] = (time.monotonic(), 200, hd, b"".join(parts))
                    _store.move_to_end(key)
                    while len(_store) > MAX:
                        _store.popitem(last=False)
            await send(m)

        await self.app(scope, receive, keep)
