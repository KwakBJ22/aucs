"""물건 상세 열람 권한과 횟수 한도(11/17 대표님).

- 상세(물건 · 서류 · 계산 · 전문가 표)는 로그인해야 봄. 목록 · 지도 · 아카데미 · 공지는 그대로 공개.
- 오픈 전(기준표 access.free_period = true): 로그인하면 전부 무료.
- 오픈 뒤: 가입한 때부터 trial_hours(24시간) 무료 → 그 뒤는 쓸 수 있는 이용권이 있어야 함(한 건 이용권은 그 물건만).
- 로봇 막기: 물건 상세를 1분 per_min · 하루 per_day 넘게 열면 잠깐 막음(429). 숫자는 기준표에서 보면서 조절.
"""

import time
from typing import Any

from fastapi import HTTPException

from aucs_api.db import connect

DEFAULT = {"free_period": True, "trial_hours": 24, "per_min": 30, "per_day": 500}
_TABLE_SQL = (
    "select value from ref.rule_tables where rule_key = 'access' and valid_from <= current_date "
    "order by valid_from desc limit 1"
)
KST_DAY = "(date_trunc('day', now() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul')"
_COUNT_SQL = f"""with ins as (insert into app.detail_views (user_id, item_id) values (%(uid)s, %(item)s))
    select count(*) filter (where at > now() - interval '1 minute') as m, count(*) as d
    from app.detail_views where user_id = %(uid)s and at >= {KST_DAY}"""
_PAID_SQL = """select 1 from app.payments
    where user_id = %(uid)s and status in ('paid', 'part_refunded') and valid_to >= current_date
      and (plan <> 'one' or item_id = %(item)s) limit 1"""
_TRIAL_SQL = (
    "select created_at > now() - make_interval(hours => %s) as ok from auth.users where id = %s"
)
_cache: tuple[float, dict[str, Any]] = (0.0, {})


def table() -> dict[str, Any]:
    """기준표 access(1분 기억). 표가 없으면(이주 0068 적용 전) 기본값 — 오픈 전 무료."""
    global _cache
    # 11/18: 처음 기억이 빈 값({})인데, 갓 켜진 서버는 monotonic() 이 60 보다 작아 그 빈 값을 돌려줬음 →
    # free_period 가 없어 오픈 전인데도 402(「하루 무료 이용이 끝났어요」). 빈 기억은 쓰지 않음.
    if _cache[1] and time.monotonic() - _cache[0] < 60:
        return _cache[1]
    try:
        with connect() as c:
            r = c.execute(_TABLE_SQL).fetchone()
        t = {**DEFAULT, **(dict(r["value"]) if r else {})}
    except Exception:  # noqa: BLE001 — 표를 못 읽어도 상세는 열리게(오픈 전 기본값)
        t = dict(DEFAULT)
    _cache = (time.monotonic(), t)
    return t


def allowed(uid: str, item_id: str | None) -> None:
    """볼 수 있는지만 봄(로그인은 이미 확인됨). 안 되면 402."""
    t = table()
    if t.get("free_period"):
        return
    with connect() as c:
        if c.execute(_PAID_SQL, {"uid": uid, "item": item_id}).fetchone():
            return
        r = c.execute(_TRIAL_SQL, (int(t.get("trial_hours") or 0), uid)).fetchone()
    if r and r["ok"]:
        return
    raise HTTPException(402, "이용권이 필요해요")


def count_view(uid: str, item_id: str) -> None:
    """물건 상세 한 번 열기 — 기록하고 한도를 넘으면 429(기록은 남김: 막힌 뒤 되풀이도 셈)."""
    t = table()
    try:
        with connect() as c:
            n = c.execute(_COUNT_SQL, {"uid": uid, "item": item_id}).fetchone() or {}
    except Exception:  # noqa: BLE001 — 기록 표가 없으면(이주 0068 적용 전) 한도 없이
        return
    if (n.get("m") or 0) >= int(t.get("per_min") or 30) or (n.get("d") or 0) >= int(
        t.get("per_day") or 500
    ):
        raise HTTPException(429, "너무 많이 열었어요 · 잠시 뒤 다시 해 주세요")
