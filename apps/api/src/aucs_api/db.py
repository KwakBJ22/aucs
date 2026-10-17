"""DB 연결 (요청마다 짧게). 비밀값은 출력하지 않습니다."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from aucs_api import settings


@contextmanager
def connect() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.connect(settings.DATABASE_URL, connect_timeout=5, row_factory=dict_row) as conn:
        yield conn
