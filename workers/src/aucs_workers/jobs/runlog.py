"""작업 실행 기록(ops.job_runs). 실패해도 기록은 남깁니다."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg


@dataclass
class Run:
    run_id: int
    count: int = 0


@contextmanager
def run(conn: psycopg.Connection, job_id: str, name_ko: str) -> Iterator[Run]:
    conn.execute(
        "insert into ops.jobs (job_id, name_ko) values (%s, %s) on conflict do nothing",
        (job_id, name_ko),
    )
    row = conn.execute(
        "insert into ops.job_runs (job_id) values (%s) returning run_id", (job_id,)
    ).fetchone()
    conn.commit()
    r = Run(run_id=int(row[0]) if row else 0)
    try:
        yield r
    except Exception as e:
        conn.rollback()
        conn.execute(
            "update ops.job_runs set finished_at = now(), status = %s, item_count = %s, message = %s "
            "where run_id = %s",
            (
                "stopped" if type(e).__name__ == "Blocked" else "failed",
                r.count,
                str(e)[:500],
                r.run_id,
            ),
        )
        conn.commit()
        raise
    conn.execute(
        "update ops.job_runs set finished_at = now(), status = 'ok', item_count = %s where run_id = %s",
        (r.count, r.run_id),
    )
    conn.commit()
