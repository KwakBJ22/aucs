"""관심도(경쟁 신호): 최근 7일 이 물건을 본 사람·관심에 담은 사람 수. 적으면 내보내지 않음(한두 명은 누군지 짐작될 수 있어서)."""

from aucs_api.db import connect

MIN_VIEWERS = 3
MIN_WATCHERS = 2

_SQL = """
select (select count(distinct coalesce(e.user_id::text, e.anon_id)) from app.events e
        where e.kind = 'item_view' and e.item_id = %(id)s and e.at > now() - interval '7 days') as viewers,
       (select count(*) from app.watch_items w where w.item_id = %(id)s) as watchers
"""


def shown(viewers: int, watchers: int) -> dict[str, int] | None:
    """보여 줄 만큼 모였을 때만 (순수 함수)."""
    if viewers < MIN_VIEWERS and watchers < MIN_WATCHERS:
        return None
    return {"viewers_7d": viewers, "watchers": watchers}


def interest(item_id: str) -> dict[str, int] | None:
    with connect() as c:
        r = c.execute(_SQL, {"id": item_id}).fetchone()
    return shown(int(r["viewers"] or 0), int(r["watchers"] or 0)) if r else None
