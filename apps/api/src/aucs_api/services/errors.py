"""오류 기록(출시 전 꼭, 10/29): 화면·API 오류를 ops.errors 에 남기고 관리자에서 묶어 봄.

밖 서비스(Sentry) 없이 우리 DB에. 같은 기기가 1분에 20건 넘게 보내면 버림(폭주 막기).
기록이 실패해도 원래 응답은 그대로(조용히 넘어감).
"""

import logging
from typing import Any

from aucs_api.db import connect

log = logging.getLogger("aucs_api.errors")
PER_MINUTE = 20


def clip(s: object, n: int) -> str | None:
    t = str(s or "").strip()
    return t[:n] or None


def save(
    side: str, message: str, *, path: str | None = None, stack: str | None = None,
    anon_id: str | None = None, agent: str | None = None,
) -> None:  # fmt: skip
    try:
        with connect() as c:
            if anon_id:
                n = c.execute(
                    "select count(*) as n from ops.errors where anon_id = %s and at > now() - interval '1 minute'",
                    (anon_id,),
                ).fetchone()
                if n and n["n"] >= PER_MINUTE:
                    return
            c.execute(
                """insert into ops.errors (side, path, message, stack, anon_id, agent)
                   values (%s, %s, %s, %s, %s, %s)""",
                (side, clip(path, 200), clip(message, 500) or "(내용 없음)", clip(stack, 4000),
                 clip(anon_id, 40), clip(agent, 200)),
            )  # fmt: skip
    except Exception:  # noqa: BLE001 — 오류 기록이 또 오류를 내면 안 됨
        log.exception("오류 기록 실패")


def recent(days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
    """최근 오류를 같은 내용끼리 묶어서: 몇 번·몇 기기·마지막 때·어느 화면."""
    with connect() as c:
        return c.execute(
            """select side, message, count(*) as n, count(distinct anon_id) as devices,
                      max(at) as last_at, (array_agg(path order by at desc))[1] as path,
                      (array_agg(stack order by at desc))[1] as stack
               from ops.errors where at > now() - make_interval(days => %s)
               group by side, message order by max(at) desc limit %s""",
            (days, limit),
        ).fetchall()
