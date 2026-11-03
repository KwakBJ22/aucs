"""DB 연결. 요청마다 새로 잇지 않고 이어 둔 연결을 돌려 씀(10/20 속도 개선). 비밀값은 출력하지 않습니다."""

import queue
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from aucs_api import settings

Conn = psycopg.Connection[dict[str, Any]]

POOL_MAX = 8  # 쉬는 연결을 이만큼까지 보관
PING_AFTER = (
    30.0  # 이보다 오래 쉰 연결은 쓰기 전에 살아 있는지 한 번 확인(새로 잇는 것보다 훨씬 빠름)
)
_idle: "queue.LifoQueue[tuple[Conn, float]]" = queue.LifoQueue(maxsize=POOL_MAX)


def _new() -> Conn:
    # Supabase 나눔 연결(6543, Vercel 용)은 미리 준비한 쿼리를 못 씀 → prepare_threshold=None (11/3)
    pooled = ":6543/" in settings.DATABASE_URL
    return psycopg.connect(
        settings.DATABASE_URL,
        connect_timeout=5,
        row_factory=dict_row,
        prepare_threshold=None if pooled else 5,
    )


def _take() -> Conn:
    while True:
        try:
            conn, at = _idle.get_nowait()
        except queue.Empty:
            return _new()
        if conn.closed:
            continue
        if time.monotonic() - at > PING_AFTER:
            try:
                conn.execute("select 1")
            except psycopg.Error:
                conn.close()
                continue
        return conn


def _give(conn: Conn) -> None:
    if conn.closed or conn.broken:
        return
    try:
        _idle.put_nowait((conn, time.monotonic()))
    except queue.Full:
        conn.close()


@contextmanager
def connect() -> Iterator[Conn]:
    """예전과 같게 쓰면 됨: 끝나면 저장(commit), 오류면 되돌림(rollback)."""
    conn = _take()
    try:
        yield conn
        conn.commit()
    except BaseException:
        try:
            conn.rollback()
        except psycopg.Error:
            conn.close()
        raise
    finally:
        if not conn.closed:
            _give(conn)


def warm(n: int = 3) -> None:
    """서버가 켜질 때 연결을 미리 몇 개 만들어 둠(첫 화면이 느리지 않게)."""
    for _ in range(n):
        try:
            _give(_new())
        except psycopg.Error:
            return


def batch(c: Conn, queries: list[tuple[str, Any]]) -> list[psycopg.Cursor[dict[str, Any]]]:
    """서로 상관없는 조회 여러 개를 한 번에 보냄(DB 왕복 1번). 결과는 돌려준 커서에서 꺼냄."""
    with c.pipeline():
        return [c.execute(q, a) for q, a in queries]
