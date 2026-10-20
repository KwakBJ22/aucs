"""누구에게나 같은 공개 자료(물건 목록·상세·전문가 표·시장)는 잠깐 보관했다 바로 돌려줌.

자료는 하루 몇 번 모으므로 2분 보관이면 충분. 로그인 정보가 붙은 요청과 GET이 아닌 요청은 보관하지 않고,
관리자가 무엇을 바꾸면(GET 아닌 요청 성공) 보관한 것을 모두 비움.
"""

import time
from collections import OrderedDict
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

TTL = 120.0
MAX = 500
PREFIXES = ("/items", "/regions", "/pro/")

_store: "OrderedDict[str, tuple[float, int, list[tuple[bytes, bytes]], bytes]]" = OrderedDict()


def clear() -> None:
    _store.clear()


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
            if status and status[0] < 400:
                clear()
            return
        if not path.startswith(PREFIXES) or b"authorization" in headers:
            await self.app(scope, receive, send)
            return
        key = path + "?" + scope.get("query_string", b"").decode()
        hit = _store.get(key)
        if hit and time.monotonic() - hit[0] < TTL:
            _, st, hd, body = hit
            await send({"type": "http.response.start", "status": st, "headers": hd})
            await send({"type": "http.response.body", "body": body})
            return
        start: dict[str, Any] = {}
        parts: list[bytes] = []

        async def keep(m: Message) -> None:
            if m["type"] == "http.response.start":
                start.update(m)
            elif m["type"] == "http.response.body":
                parts.append(m.get("body", b""))
                if not m.get("more_body") and start.get("status") == 200:
                    hd = [
                        (k, v)
                        for k, v in start.get("headers", [])
                        if k.lower() not in (b"access-control-allow-origin", b"vary")
                    ]
                    _store[key] = (time.monotonic(), 200, hd, b"".join(parts))
                    _store.move_to_end(key)
                    while len(_store) > MAX:
                        _store.popitem(last=False)
            await send(m)

        await self.app(scope, receive, keep)
