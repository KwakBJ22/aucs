"""관리자 「알림 보내기」(11/12, 기능명세서 6): 대상 고르기 → 대상 수 미리 보기 → 바로 또는 예약.

실제로 알림함에 넣고 휴대폰으로 보내는 일은 PC 의 5분 작업(aucs_workers.ops_watch.send_broadcasts)이 함.
대상 조건 · 밤 시간 판단은 그 모듈 한 곳에 있음 — 미리 보기 수와 보낸 수가 같은 조건.
"""

from datetime import UTC, datetime
from typing import Any

from aucs_workers.ops_watch import QUIET, count_target, quiet, seoul_hour
from psycopg.types.json import Jsonb

from aucs_api.db import connect
from aucs_api.services.admin_ops import audit


class SendError(ValueError):
    """화면에 그대로 보일 까닭."""


def _target(t: dict[str, Any]) -> dict[str, Any]:
    kind = t.get("kind") if t.get("kind") in ("all", "region", "paid", "free") else "all"
    if kind != "region":
        return {"kind": kind}
    regions = [str(x).strip() for x in t.get("regions") or [] if str(x).strip()][:30]
    if not regions:
        raise SendError("지역을 하나 이상 적어 주세요")
    return {"kind": "region", "regions": regions}


def preview(t: dict[str, Any]) -> dict[str, int]:
    """대상 회원 수 · 휴대폰 알림을 켠 수."""
    with connect() as c:
        n: dict[str, int] = count_target(c, _target(t))
    return n


def broadcasts() -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            """select bc_id, title, body, link, target, send_at, status, sent_n, sent_at, created_at
               from app.broadcasts order by bc_id desc limit 30"""
        ).fetchall()


def create(actor: str | None, title: str, body: str, link: str | None, t: dict[str, Any],
           send_at: datetime | None) -> dict[str, Any]:  # fmt: skip
    """알림 하나 만들기. 바로(send_at 없음)는 PC 가 5분 안에 보냄. 밤 9시~아침 8시는 막음."""
    when = send_at or datetime.now(UTC)
    if when.tzinfo is None:
        raise SendError("시각에 시간대가 없어요")
    if quiet(seoul_hour(when.astimezone(UTC))):
        raise SendError(
            f"밤 {QUIET[0] - 12}시 ~ 아침 {QUIET[1]}시에는 보내지 않아요 · 낮 시간으로 예약해 주세요"
        )
    if link and not link.startswith("/"):
        raise SendError("누르면 갈 곳은 우리 주소만(/로 시작) 넣을 수 있어요")
    tg = _target(t)
    with connect() as c:
        n = count_target(c, tg)
        r = c.execute(
            """insert into app.broadcasts (title, body, link, target, send_at, created_by)
               values (%s,%s,%s,%s,%s,%s) returning bc_id""",
            (title, body, link or None, Jsonb(tg), when, actor),
        ).fetchone()
        audit(c, actor, "broadcast", str(r["bc_id"]) if r else "-", None,
              {"title": title, "target": tg, "send_at": when.isoformat(), "users": n["users"]})  # fmt: skip
    return {"bc_id": r["bc_id"] if r else None, **n}


def cancel(actor: str | None, bc_id: int) -> bool:
    """보내기 전 알림만 취소."""
    with connect() as c:
        r = c.execute(
            "update app.broadcasts set status = 'cancelled' where bc_id = %s and status = 'waiting' returning bc_id",
            (bc_id,),
        ).fetchone()
        if r:
            audit(c, actor, "broadcast_cancel", str(bc_id))
    return bool(r)
