"""운영 지켜보기(11/12): 빨간 불 판단 · 관리자 휴대폰 알림 · 관리자가 쓴 알림 보내기.

빨간 불 판단은 여기 한 곳 — 관리자 「오늘」 화면(API admin_ops.today)과 PC 의 5분 작업이 같이 부름.
"""

from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

DB_LIMIT = 8 * 1024 * 1024 * 1024
DAILY_JOBS = ("court_results", "court_items", "analyze", "court_docs", "notify")  # 아침 묶음 순서
QUIET = (21, 8)  # 밤 9시 ~ 아침 8시(한국)에는 회원 알림을 보내지 않음
ADMIN_QUIET = (23, 7)  # 빨간 불은 밤 11시 ~ 아침 7시만 쉼(아침에 한꺼번에)


def _hours(t: Any) -> float:
    return float((datetime.now(UTC) - t).total_seconds()) / 3600


def seoul_hour(now: datetime | None = None) -> int:
    """지금 한국 시각(시)."""
    n = now or datetime.now(UTC)
    return (n.hour + 9) % 24


def quiet(hour: int, span: tuple[int, int] = QUIET) -> bool:
    """밤 시간(span[0]시부터 다음 날 span[1]시 전)인가."""
    start, end = span
    return hour >= start or hour < end


def red_lights(conn: psycopg.Connection[Any]) -> list[dict[str, str]]:
    """빨간 불 모음: 멈춘·실패한 작업 · 하루 넘게 안 돈 아침 작업 · 같은 오류 몰림 · 밀린 제보·문의 · DB 80% · 백업 8일.

    key 는 같은 빨간 불을 하루 한 번만 알리는 데 씀(건수가 바뀌어도 같은 key)."""
    cur = conn.cursor(row_factory=dict_row)
    last = cur.execute(
        """select distinct on (r.job_id) r.job_id, j.name_ko, r.started_at, r.finished_at, r.status,
                  to_jsonb(r) ->> 'acked_at' as acked_at
           from ops.job_runs r join ops.jobs j using (job_id) order by r.job_id, r.started_at desc"""
    ).fetchall()
    n = (
        cur.execute(
            """select
            (select count(*) from app.value_reports where status = 'open' and created_at < now() - interval '2 days') as reports_late,
            (select count(*) from app.inquiries where answered_at is null and created_at < now() - interval '2 days') as inq_late,
            pg_database_size(current_database()) as db_bytes"""
        ).fetchone()
        or {}
    )
    burst = cur.execute(
        """select message, count(*) as n from ops.errors where at > now() - interval '1 hour'
           group by message having count(*) >= 5 order by 2 desc limit 3"""
    ).fetchall()
    by = {j["job_id"]: j for j in last}
    red: list[dict[str, str]] = []
    for j in last:
        # 관리자가 「확인함」 한 실패는 뺌(11/14)
        if j["status"] in ("failed", "stopped") and not j["acked_at"]:
            word = "실패" if j["status"] == "failed" else "멈춤"
            red.append({"kind": "job", "key": f"job:{j['job_id']}:{j['status']}",
                        "text": f"{j['name_ko']} 작업이 {word}", "go": "jobs"})  # fmt: skip
        elif j["status"] == "running" and j["started_at"] and _hours(j["started_at"]) > 6:
            red.append({"kind": "job", "key": f"job:{j['job_id']}:long",
                        "text": f"{j['name_ko']} 작업이 6시간 넘게 도는 중", "go": "jobs"})  # fmt: skip
    for k in DAILY_JOBS:
        dj = by.get(k)
        if dj and dj["started_at"] and _hours(dj["started_at"]) > 26:
            red.append({"kind": "job", "key": f"job:{k}:late",
                        "text": f"{dj['name_ko']} 작업이 하루 넘게 안 돎", "go": "jobs"})  # fmt: skip
    for b in burst:
        red.append({"kind": "error", "key": f"error:{b['message'][:60]}",
                    "text": f"같은 오류가 1시간에 {b['n']}번 · {b['message'][:60]}", "go": "jobs"})  # fmt: skip
    if n.get("reports_late"):
        red.append({"kind": "review", "key": "reports_late",
                    "text": f"제보 {n['reports_late']}건이 2일 넘게 밀림", "go": "review"})  # fmt: skip
    if n.get("inq_late"):
        red.append({"kind": "member", "key": "inq_late",
                    "text": f"문의 {n['inq_late']}건이 2일 넘게 밀림", "go": "members"})  # fmt: skip
    if n.get("db_bytes", 0) > DB_LIMIT * 0.8:
        red.append({"kind": "db", "key": "db80", "text": "DB 용량이 80%를 넘음", "go": "today"})
    bk = by.get("backup")
    if not bk or bk["status"] != "ok" or _hours(bk["finished_at"] or bk["started_at"]) > 24 * 8:
        red.append({"kind": "db", "key": "backup", "text": "백업이 8일 넘게 없음", "go": "today"})
    return red


def alert_admins(conn: psycopg.Connection[Any], now: datetime | None = None) -> int:
    """새 빨간 불을 대표·운영자 알림함에 넣음(같은 것은 하루 한 번, 밤 11시~아침 7시는 쉼). 넣은 수."""
    if quiet(seoul_hour(now), ADMIN_QUIET):
        return 0
    admins = [r[0] for r in conn.execute(
        "select user_id from app.admins where role in ('owner','operator')"
    ).fetchall()]  # fmt: skip
    if not admins:
        return 0
    n = 0
    for r in red_lights(conn):
        new = conn.execute(
            "insert into ops.admin_alerts (alert_key, text) values (%s, %s) on conflict do nothing returning 1",
            (r["key"], r["text"]),
        ).fetchone()
        if not new:
            continue
        for uid in admins:
            conn.execute(
                "insert into app.notifications (user_id, title, body, link) values (%s, %s, %s, %s)",
                (uid, "옥스 관리자 · 빨간 불", r["text"], "/admin"),
            )
        n += 1
    return n


# ── 알림 보내기(관리자가 쓴 것) ─────────────────────────────


def target_where(target: dict[str, Any]) -> tuple[str, list[Any]]:
    """보낼 대상 → auth.users u 에 붙일 조건. 미리 보기 수(API)와 실제 보내기(여기)가 같은 조건을 씀."""
    kind = target.get("kind", "all")
    if kind == "region":
        names = [str(x).strip() for x in target.get("regions") or [] if str(x).strip()]
        return (
            "exists (select 1 from app.profiles p where p.user_id = u.id and p.interest_regions && %s::text[])",
            [names],
        )
    paid = """(exists (select 1 from app.grants g where g.user_id = u.id and g.until_date >= current_date)
               or exists (select 1 from app.payments y where y.user_id = u.id
                          and y.status in ('paid','part_refunded') and y.valid_to >= current_date))"""
    if kind == "paid":
        return paid, []
    if kind == "free":
        return f"not {paid}", []
    return "true", []


def count_target(conn: psycopg.Connection[Any], target: dict[str, Any]) -> dict[str, int]:
    """대상 회원 수 · 그중 휴대폰 알림을 켠 회원 수(이용 제한 회원은 뺌)."""
    where, args = target_where(target)
    r = (
        conn.cursor(row_factory=dict_row)
        .execute(
            f"""select count(*) as users,
                   count(*) filter (where exists (select 1 from app.push_subscriptions s where s.user_id = u.id)) as push
            from auth.users u
            where {where} and not exists (select 1 from app.user_limits l where l.user_id = u.id)""",
            args,
        )
        .fetchone()
    )
    return {"users": int(r["users"]), "push": int(r["push"])} if r else {"users": 0, "push": 0}


def send_broadcasts(conn: psycopg.Connection[Any], now: datetime | None = None) -> int:
    """때가 된 알림을 알림함에 넣음(밤 9시~아침 8시는 기다림). 보낸 회원 수 합."""
    if quiet(seoul_hour(now)):
        return 0
    total = 0
    for bc_id, title, body, link, target in conn.execute(
        """select bc_id, title, body, link, target from app.broadcasts
           where status = 'waiting' and send_at <= now() order by send_at for update skip locked"""
    ).fetchall():
        where, args = target_where(dict(target or {}))
        cur = conn.execute(
            f"""insert into app.notifications (user_id, title, body, link)
                select u.id, %s, %s, %s from auth.users u
                where {where} and not exists (select 1 from app.user_limits l where l.user_id = u.id)""",
            [title, body, link or "/notifications", *args],
        )
        sent = cur.rowcount or 0
        conn.execute(
            "update app.broadcasts set status = 'sent', sent_n = %s, sent_at = now() where bc_id = %s",
            (sent, bc_id),
        )
        total += sent
    return total


def run_once() -> str:
    """5분마다(관리자_요청 작업): 빨간 불 알림 · 때가 된 알림 보내기 → 휴대폰으로."""
    from aucs_workers.db import connect
    from aucs_workers.jobs.notify import send_pushes

    with connect() as conn:
        a = alert_admins(conn)
        b = send_broadcasts(conn)
        conn.commit()
        p = send_pushes(conn) if (a or b) else 0
        conn.commit()
    return f"빨간 불 {a} · 보낸 알림 {b}명 · 푸시 {p}"
