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
IDLE_MAX = 60.0  # 이보다 오래 쉰 연결은 버림(중계 서버가 끊었을 수 있음)
_idle: "queue.LifoQueue[tuple[Conn, float]]" = queue.LifoQueue(maxsize=POOL_MAX)


def _new() -> Conn:
    return psycopg.connect(settings.DATABASE_URL, connect_timeout=5, row_factory=dict_row)


def _take() -> Conn:
    while True:
        try:
            conn, at = _idle.get_nowait()
        except queue.Empty:
            return _new()
        if conn.closed or time.monotonic() - at > IDLE_MAX:
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
