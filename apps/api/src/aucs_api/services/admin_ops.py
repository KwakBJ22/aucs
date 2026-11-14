"""관리자 모드 1단계(11/2): 오늘·작업·검수·회원·문의·공지·설정·감사 기록.

바꾸는 일은 모두 ops.audit_log 에 남김(누가·무엇을·전/후). 회원 메일은 가려서 보여 주고, 「보기」를 누르면 기록.
수집 원본(raw)은 고치지 않음. 고친 값은 따로(previous_value·signal_overrides) 저장.
"""

from datetime import date, timedelta
from typing import Any

from aucs_workers.ops_watch import DB_LIMIT, red_lights
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

from aucs_api.db import connect

REQUESTABLE = {
    "daily": "아침 묶음 전체", "results": "법원 매각결과", "items": "법원 경매 물건", "docs": "사건 서류",
    "analyze": "물건 분석", "notify": "알림", "buildings": "건축물대장", "onbid": "공매(온비드)",
    "trades": "실거래가", "redev": "정비사업", "watched": "관심 바로 준비", "regions": "법정동 표",
}  # fmt: skip
PLANS = ("basic", "pro")


def audit(c: Any, actor: str | None, action: str, target: str, before: Any = None,
          after: Any = None, note: str | None = None) -> None:  # fmt: skip
    """감사 기록 한 줄(고치거나 지울 수 없음)."""
    c.execute(
        "insert into ops.audit_log (actor_id, action, target, before_val, after_val, note) values (%s,%s,%s,%s,%s,%s)",
        (actor, action, target, Jsonb(before) if before is not None else None,
         Jsonb(after) if after is not None else None, note),
    )  # fmt: skip


def mask(email: str | None) -> str:
    if not email or "@" not in email:
        return "-"
    name, dom = email.split("@", 1)
    return f"{name[:3]}***@{dom}"


# ── 1 오늘 ────────────────────────────────────────────


# 아침 묶음 순서(화면용). 빨간 불의 「하루 넘게 안 돎」 판단(DAILY_JOBS)과는 따로 — 그쪽은 알림이 걸려 있음
MORNING = ("court_results", "court_items", "buildings", "official_prices", "land_use", "onbid",
           "analyze", "notify")  # fmt: skip
# 오늘 0시(한국). DB 는 UTC 라 current_date 로 자르면 아침 6시 묶음이 「어제」로 빠짐(11/14)
KST_DAY = "(date_trunc('day', now() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul')"


def _todo(red: list[dict[str, str]], n: dict[str, Any], tmp: list[str]) -> list[dict[str, Any]]:
    """하실 일: 대표님이 눌러야 끝나는 것만. 빨간 불(판단은 ops_watch 한 곳) + 기다리는 확인·답."""
    out: list[dict[str, Any]] = []
    for r in red:
        if r["key"] in ("reports_late", "inq_late"):  # 아래 건수 줄과 겹침
            continue
        t: dict[str, Any] = {"key": r["key"], "text": r["text"], "go": r["go"], "red": True}
        p = r["key"].split(":")
        if r["kind"] == "job" and len(p) == 3 and p[2] in ("failed", "stopped"):
            t["ack_job"] = p[1]  # 다시 돌릴 일이 아니면 「확인함」으로 넘김
        out.append(t)
    for key, text, go in (
        ("review_wait", "감정평가서 확인 {}건 · 기계가 못 가른 것", "review"),
        ("reports_open", "제보 {}건", "review"),
        ("inq_open", "답 안 한 문의 {}건", "members"),
        ("refunds_wait", "환불 요청 {}건", "members"),
    ):
        if n.get(key):
            out.append({"key": key, "text": text.format(n[key]), "go": go})
    if tmp:
        out.append({"key": "rule_tmp", "go": "settings",
                    "text": f"기준표 임시값 {len(tmp)}개 · {', '.join(tmp)}"})  # fmt: skip
    return out


def today() -> dict[str, Any]:
    with connect() as c:
        last = c.execute(
            """select distinct on (r.job_id) r.job_id, j.name_ko, r.started_at, r.finished_at, r.status,
                      r.item_count, left(r.message, 200) as message
               from ops.job_runs r join ops.jobs j using (job_id) order by r.job_id, r.started_at desc"""
        ).fetchall()
        n = (
            c.execute(
                f"""select
                (select count(*) from core.items where sale_date >= (now() at time zone 'Asia/Seoul')::date
                   and status_code is distinct from 'gone') as items,
                (select count(*) from auth.users where created_at >= {KST_DAY} - interval '1 day' and created_at < {KST_DAY}) as new_users,
                (select count(distinct anon_id) from app.events where at >= {KST_DAY} - interval '1 day' and at < {KST_DAY}) as devices,
                (select count(*) from app.events where kind = 'item_view' and at >= {KST_DAY} - interval '1 day' and at < {KST_DAY}) as views,
                (select count(*) from ops.errors where at >= {KST_DAY} - interval '1 day' and at < {KST_DAY}) as errors,
                (select count(*) from app.value_reports where status = 'open') as reports_open,
                (select count(*) from app.inquiries where answered_at is null) as inq_open,
                (select count(*) from app.refund_requests where status = 'waiting') as refunds_wait,
                (select count(*) from app.contrib_uploads where kind = 'appraisal' and status = 'review'
                   and note in ('ocr_none', 'ocr_other')) as review_wait,
                (select count(distinct user_id) from app.academy_progress) as academy_users,
                (select count(*) from app.academy_progress where key not like 'task:%') as academy_lessons,
                (select max(computed_at) from analysis.pick_scores) as picks_at,
                (select max(computed_at) < now() - interval '36 hours' from analysis.pick_scores) as picks_stale,
                pg_database_size(current_database()) as db_bytes"""
            ).fetchone()
            or {}
        )
        tmp = [r["rule_key"] for r in c.execute(
            """select rule_key from ref.rule_tables
               where reviewed_at is null and valid_to is null and basis like '%임시값%' order by 1"""
        ).fetchall()]  # fmt: skip
        # 유료 전환 가늠(11/12 대표님): 회원이 관심 담은 진행 물건 중 서류가 찬 비율 — 80% 넘으면 전환
        fill = (
            c.execute(
                """with w as (select distinct i.item_id, i.case_id from app.watch_items w
                              join core.items i using (item_id) where i.sale_date >= current_date)
                select (select count(*) from auth.users) as members,
                  (select count(distinct user_id) from app.contrib_uploads where points > 0) as uploaders,
                  (select count(*) from app.contrib_uploads where points > 0 and created_at > now() - interval '7 days') as week,
                  count(*) as watched,
                  count(*) filter (where exists (select 1 from app.uploaded_registries r where r.item_id = w.item_id and r.shared)) as registry,
                  count(*) filter (where exists (select 1 from core.appraisal_files f where f.case_id = w.case_id)) as appraisal
                from w"""
            ).fetchone()
            or {}
        )
        steps = c.execute(
            f"""select r.job_id, j.name_ko, sum(r.item_count)::int as item_count,
                      (array_agg(r.status order by r.started_at desc))[1] as status,
                      min(r.started_at) as started_at, max(r.finished_at) as finished_at
               from ops.job_runs r join ops.jobs j using (job_id)
               where r.job_id = any(%s) and r.started_at >= {KST_DAY} group by r.job_id, j.name_ko""",
            (list(MORNING),),
        ).fetchall()
        red = red_lights(c)  # 빨간 불 판단은 한 곳(PC 휴대폰 알림과 같음, 11/12)
    by = {j["job_id"]: j for j in last}
    bk = by.get("backup")
    rt = by.get("restore_test")
    hourly = by.get("court_docs")
    return {
        "todo": _todo(red, n, tmp),
        "collect": {
            "morning": [s for k in MORNING for s in steps if s["job_id"] == k],
            "morning_total": len(MORNING),
            "hourly": hourly
            and {
                k: hourly[k] for k in ("job_id", "name_ko", "status", "started_at", "finished_at")
            },
            "picks": {"at": n.get("picks_at"), "stale": bool(n.get("picks_stale"))},
        },
        "service": {
            **{k: n.get(k, 0) for k in ("items", "new_users", "devices", "views", "errors")},
            "academy": {"users": n.get("academy_users", 0), "lessons": n.get("academy_lessons", 0)},
        },
        "fill": dict(fill),
        "db": {"used": n.get("db_bytes", 0), "limit": DB_LIMIT},
        "backup": bk
        and {
            "at": bk["finished_at"] or bk["started_at"],
            "status": bk["status"],
            "message": bk["message"],
        },
        "restore": rt and {"at": rt["finished_at"] or rt["started_at"], "status": rt["status"]},
    }


def ack_job(actor: str | None, job_id: str) -> bool | None:
    """실패·멈춤으로 끝난 마지막 실행을 「확인함」 — 빨간 불에서 빠짐(기록은 그대로). 칸이 없으면(이주 0055 전) None."""
    try:
        with connect() as c:
            row = c.execute(
                """update ops.job_runs set acked_at = now()
                   where run_id = (select run_id from ops.job_runs where job_id = %s order by started_at desc limit 1)
                     and status in ('failed', 'stopped') returning run_id""",
                (job_id,),
            ).fetchone()
            if row:
                audit(c, actor, "job_ack", job_id, None, {"run_id": row["run_id"]})
    except pg_errors.UndefinedColumn:
        return None
    return bool(row)


# ── 2 작업·수집 ───────────────────────────────────────


def jobs() -> dict[str, Any]:
    with connect() as c:
        rows = c.execute(
            """with d as (select job_id, started_at::date as day,
                          bool_or(status = 'failed' or status = 'stopped') as bad, bool_or(status = 'ok') as ok
                          from ops.job_runs where started_at >= current_date - 13 group by 1, 2)
               select j.job_id, j.name_ko, l.started_at, l.finished_at, l.status, l.item_count, left(l.message, 300) as message,
                      coalesce((select json_agg(json_build_object('day', d.day, 's', case when d.bad then 'bad' when d.ok then 'ok' else 'run' end) order by d.day)
                                from d where d.job_id = j.job_id), '[]') as days
               from ops.jobs j
               left join lateral (select * from ops.job_runs r where r.job_id = j.job_id order by started_at desc limit 1) l on true
               order by l.started_at desc nulls last"""
        ).fetchall()
        reqs = c.execute(
            """select req_id, job_key, requested_at, status, started_at, finished_at, left(message, 200) as message
               from ops.job_requests order by req_id desc limit 20"""
        ).fetchall()
    first = date.today() - timedelta(days=13)
    return {
        "jobs": rows,
        "requests": reqs,
        "first_day": first.isoformat(),
        "requestable": REQUESTABLE,
    }


def mark_stale(actor: str | None) -> int:
    with connect() as c:
        rows = c.execute(
            """update ops.job_runs set status = 'stopped', finished_at = now(),
                      message = coalesce(message || ' · ', '') || '관리자가 멈춤으로 정리'
               where status = 'running' and started_at < now() - interval '6 hours' returning run_id"""
        ).fetchall()
        if rows:
            audit(
                c,
                actor,
                "jobs_mark_stale",
                "ops.job_runs",
                None,
                {"run_ids": [r["run_id"] for r in rows]},
            )
    return len(rows)


def request_job(actor: str | None, key: str) -> dict[str, Any] | None:
    ok = key in REQUESTABLE or (key.startswith("analyze_item:") and 3 < len(key) < 120)
    if not ok:
        return None
    with connect() as c:
        dup = c.execute(
            "select req_id from ops.job_requests where job_key = %s and status in ('waiting','running')",
            (key,),
        ).fetchone()
        if dup:
            return {"req_id": dup["req_id"], "dup": True}
        row = c.execute(
            "insert into ops.job_requests (job_key, requested_by) values (%s, %s) returning req_id",
            (key, actor),
        ).fetchone()
        audit(c, actor, "job_request", key)
    return {"req_id": row["req_id"] if row else None, "dup": False}


def errors(days: int = 7) -> list[dict[str, Any]]:
    """최근 오류(같은 내용끼리). 「고침」 누른 뒤 다시 안 난 것은 뺌."""
    with connect() as c:
        return c.execute(
            """with f as (select target, max(at) as fixed_at from ops.audit_log where action = 'error_fixed' group by 1)
               select e.side, e.message, count(*) as n, count(distinct e.anon_id) as devices, max(e.at) as last_at,
                      (array_agg(e.path order by e.at desc))[1] as path, (array_agg(e.stack order by e.at desc))[1] as stack
               from ops.errors e left join f on f.target = e.side || '|' || e.message
               where e.at > now() - make_interval(days => %s) and (f.fixed_at is null or e.at > f.fixed_at)
               group by e.side, e.message order by max(e.at) desc limit 50""",
            (days,),
        ).fetchall()


def error_fixed(actor: str | None, side: str, message: str) -> None:
    with connect() as c:
        audit(c, actor, "error_fixed", f"{side}|{message}")


# ── 3 자료 검수 ───────────────────────────────────────


def review(limit: int = 50) -> dict[str, Any]:
    with connect() as c:
        reports = c.execute(
            """select r.report_id, r.item_id, r.section, r.note, r.created_at, i.address, i.sale_date
               from app.value_reports r left join core.items i using (item_id)
               where r.status = 'open' order by r.created_at limit %s""",
            (limit,),
        ).fetchall()
        fields = c.execute(
            """select f.field_id, d.case_id, d.doc_kind, f.field, f.value, left(f.raw_text, 200) as raw_text, f.confidence,
                      (select min(sale_date) from core.items i where i.case_id = d.case_id and i.sale_date >= current_date) as sale_date
               from core.extracted_fields f join core.documents d using (doc_id)
               where f.check_status = 'needs_review' order by sale_date nulls last, f.field_id limit %s""",
            (limit,),
        ).fetchall()
        signals = c.execute(
            """select s.signal_id, s.item_id, s.rule_id, s.level, s.title, s.evidence, i.sale_date, i.address
               from analysis.risk_signals s join core.items i using (item_id)
               where s.status = '확인 필요' and i.sale_date >= current_date and s.level <> 'info'
                 and not exists (select 1 from analysis.signal_overrides o where o.item_id = s.item_id and o.rule_id = s.rule_id)
               order by s.rule_id = 'risk.special_condition',
                        array_position(array['fatal','high','mid','low'], s.level), i.sale_date, s.item_id
               limit %s""",
            (limit,),
        ).fetchall()
        total = c.execute(
            """select (select count(*) from app.value_reports where status = 'open') as reports,
                      (select count(*) from core.extracted_fields where check_status = 'needs_review') as fields,
                      (select count(*) from analysis.risk_signals s join core.items i using (item_id)
                        where s.status = '확인 필요' and i.sale_date >= current_date and s.level <> 'info'
                          and not exists (select 1 from analysis.signal_overrides o
                                          where o.item_id = s.item_id and o.rule_id = s.rule_id)) as signals"""
        ).fetchone()
    return {"reports": reports, "fields": fields, "signals": signals, "total": total}


def check_field(actor: str | None, field_id: int, value: Any | None) -> bool:
    """칸 검수: value 가 없으면 「맞음」, 있으면 고친 값(원래 값은 previous_value 에)."""
    with connect() as c:
        before = c.execute(
            "select value from core.extracted_fields where field_id = %s", (field_id,)
        ).fetchone()
        if not before:
            return False
        if value is None:
            c.execute(
                "update core.extracted_fields set check_status = 'confirmed', corrected_by = %s, corrected_at = now() where field_id = %s",
                (actor, field_id),
            )
        else:
            c.execute(
                """update core.extracted_fields set previous_value = value, value = %s, method = 'manual',
                          check_status = 'confirmed', corrected_by = %s, corrected_at = now() where field_id = %s""",
                (Jsonb(value), actor, field_id),
            )
        audit(c, actor, "field_check", str(field_id), before["value"], value)
    return True


def decide_signal(actor: str | None, item_id: str, rule_id: str, status: str) -> bool:
    """위험 신호 판단(확정/없음). 분석을 다시 돌려도 남도록 signal_overrides 에 저장."""
    with connect() as c:
        s = c.execute(
            "select status from analysis.risk_signals where item_id = %s and rule_id = %s limit 1",
            (item_id, rule_id),
        ).fetchone()
        if not s:
            return False
        c.execute(
            """insert into analysis.signal_overrides (item_id, rule_id, status, decided_by) values (%s,%s,%s,%s)
               on conflict (item_id, rule_id) do update set status = excluded.status, decided_by = excluded.decided_by, decided_at = now()""",
            (item_id, rule_id, status, actor),
        )
        c.execute(
            "update analysis.risk_signals set status = %s where item_id = %s and rule_id = %s",
            ("확정" if status == "확정" else "모름", item_id, rule_id),
        )
        if status == "없음":
            c.execute(
                "delete from analysis.risk_signals where item_id = %s and rule_id = %s",
                (item_id, rule_id),
            )
        audit(
            c,
            actor,
            "signal_decide",
            f"{item_id}|{rule_id}",
            {"status": s["status"]},
            {"status": status},
        )
    return True


# ── 4 회원 ────────────────────────────────────────────


def users(q: str = "", limit: int = 100) -> list[dict[str, Any]]:
    like = f"%{q.strip()}%"
    with connect() as c:
        rows = c.execute(
            """select u.id as user_id, u.email, u.created_at, u.last_sign_in_at, p.nickname,
                      (select plan || ' · ' || max(until_date) from app.grants g where g.user_id = u.id and g.until_date >= current_date group by plan order by max(until_date) desc limit 1) as plan,
                      (select count(*) from app.watch_items w where w.user_id = u.id) as watch_n,
                      exists (select 1 from app.user_limits l where l.user_id = u.id) as limited,
                      (select role from app.admins a where a.user_id = u.id) as admin_role
               from auth.users u left join app.profiles p on p.user_id = u.id
               where %s = '' or u.email ilike %s or p.nickname ilike %s
               order by u.created_at desc limit %s""",
            (q.strip(), like, like, limit),
        ).fetchall()
    for r in rows:
        r["email"] = mask(r["email"])
    return rows


def user_detail(uid: str) -> dict[str, Any] | None:
    with connect() as c:
        u = c.execute(
            """select u.id as user_id, u.email, u.created_at, u.last_sign_in_at, p.nickname, p.interest_regions, p.purpose,
                      (select count(*) from app.watch_items where user_id = u.id) as watch_n,
                      (select count(*) from app.saved_searches where user_id = u.id) as search_n,
                      (select count(*) from app.notifications where user_id = u.id) as noti_n,
                      (select count(*) from app.bid_results where user_id = u.id) as bid_n,
                      (select count(*) from app.uploaded_registries where user_id = u.id) as registry_n,
                      (select count(*) from app.mock_bids where user_id = u.id) as mock_n,
                      (select reason from app.user_limits where user_id = u.id) as limit_reason
               from auth.users u left join app.profiles p on p.user_id = u.id where u.id = %s""",
            (uid,),
        ).fetchone()
        if not u:
            return None
        u["email"] = mask(u["email"])
        b = c.execute(
            """select coalesce(sum(delta) filter (where delta > 0 and (expires_at is null or expires_at > now())), 0)
                      + coalesce(sum(delta) filter (where delta < 0), 0) as b from app.point_ledger where user_id = %s""",
            (uid,),
        ).fetchone()  # fmt: skip
        u["points"] = max(0, int(b["b"])) if b else 0
        u["grants"] = c.execute(
            "select plan, until_date, reason, created_at from app.grants where user_id = %s order by created_at desc",
            (uid,),
        ).fetchall()
        u["inquiries"] = c.execute(
            "select inquiry_id, body, answer, created_at, answered_at from app.inquiries where user_id = %s order by created_at desc limit 20",
            (uid,),
        ).fetchall()
    return u


def reveal_email(actor: str | None, uid: str) -> str | None:
    with connect() as c:
        r = c.execute("select email from auth.users where id = %s", (uid,)).fetchone()
        if r:
            audit(c, actor, "email_view", uid)
    return r["email"] if r else None


def grant(actor: str | None, uid: str, plan: str, days: int, reason: str) -> dict[str, Any] | None:
    if plan not in PLANS:
        return None
    until = date.today() + timedelta(days=days)
    with connect() as c:
        if not c.execute("select 1 from auth.users where id = %s", (uid,)).fetchone():
            return None
        c.execute(
            "insert into app.grants (user_id, plan, until_date, reason, granted_by) values (%s,%s,%s,%s,%s)",
            (uid, plan, until, reason, actor),
        )
        c.execute(
            "insert into app.notifications (user_id, title, body, link) values (%s, %s, %s, '/plans')",
            (uid, "이용권을 받았어요", f"{until.month}월 {until.day}일까지 쓸 수 있어요"),
        )
        audit(c, actor, "grant", uid, None, {"plan": plan, "until": until.isoformat()}, reason)
    return {"plan": plan, "until_date": until.isoformat()}


def set_limit(actor: str | None, uid: str, reason: str | None) -> bool:
    """이용 제한 걸기(reason 있음)·풀기(None). 회원에게 알림."""
    with connect() as c:
        if not c.execute("select 1 from auth.users where id = %s", (uid,)).fetchone():
            return False
        if reason:
            c.execute(
                """insert into app.user_limits (user_id, reason, limited_by) values (%s,%s,%s)
                   on conflict (user_id) do update set reason = excluded.reason, limited_by = excluded.limited_by, created_at = now()""",
                (uid, reason, actor),
            )
            c.execute(
                "insert into app.notifications (user_id, title, body, link) values (%s,%s,%s,'/more')",
                (uid, "이용이 잠시 제한됐어요", f"이유: {reason} · 문의로 알려 주세요"),
            )
        else:
            c.execute("delete from app.user_limits where user_id = %s", (uid,))
        audit(c, actor, "limit" if reason else "unlimit", uid, None, None, reason)
    return True


def is_limited(uid: str) -> bool:
    with connect() as c:
        return (
            c.execute("select 1 from app.user_limits where user_id = %s", (uid,)).fetchone()
            is not None
        )


# ── 문의 ──────────────────────────────────────────────


def inquiries(only_open: bool = True) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            """select q.inquiry_id, q.user_id, u.email, q.body, q.answer, q.created_at, q.answered_at
               from app.inquiries q left join auth.users u on u.id = q.user_id
               where not %s or q.answered_at is null order by q.created_at limit 100""",
            (only_open,),
        ).fetchall()
    for r in rows:
        r["email"] = mask(r["email"])
    return rows


def answer(actor: str | None, inquiry_id: int, text: str) -> bool:
    with connect() as c:
        r = c.execute(
            """update app.inquiries set answer = %s, answered_by = %s, answered_at = now()
               where inquiry_id = %s returning user_id""",
            (text, actor, inquiry_id),
        ).fetchone()
        if not r:
            return False
        if r["user_id"]:
            c.execute(
                "insert into app.notifications (user_id, title, body, link) values (%s,%s,%s,'/more#ask')",
                (r["user_id"], "문의에 답했어요", text[:80]),
            )
        audit(c, actor, "inquiry_answer", str(inquiry_id))
    return True


def ask(uid: str, body: str) -> int:
    with connect() as c:
        r = c.execute(
            "insert into app.inquiries (user_id, body) values (%s,%s) returning inquiry_id",
            (uid, body),
        ).fetchone()
    return int(r["inquiry_id"]) if r else 0


def my_inquiries(uid: str) -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            "select inquiry_id, body, answer, created_at, answered_at from app.inquiries where user_id = %s order by created_at desc limit 20",
            (uid,),
        ).fetchall()


# ── 6 공지 ────────────────────────────────────────────


def notices(active_only: bool) -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            """select notice_id, title, body, start_at, end_at, pinned, created_at from app.notices
               where not %s or (start_at <= now() and (end_at is null or end_at > now()))
               order by pinned desc, start_at desc limit 50""",
            (active_only,),
        ).fetchall()


def save_notice(actor: str | None, nid: int | None, d: dict[str, Any]) -> dict[str, Any] | None:
    with connect() as c:
        if nid is None:
            row = c.execute(
                """insert into app.notices (title, body, start_at, end_at, pinned, created_by)
                   values (%s,%s,coalesce(%s, now()),%s,%s,%s) returning *""",
                (
                    d["title"],
                    d.get("body", ""),
                    d.get("start_at"),
                    d.get("end_at"),
                    d.get("pinned", False),
                    actor,
                ),
            ).fetchone()
            audit(c, actor, "notice_add", str(row["notice_id"]) if row else "", None, d)
        else:
            before = c.execute(
                "select title, body, end_at, pinned from app.notices where notice_id = %s", (nid,)
            ).fetchone()
            if not before:
                return None
            row = c.execute(
                """update app.notices set title = %s, body = %s, start_at = coalesce(%s, start_at), end_at = %s, pinned = %s
                   where notice_id = %s returning *""",
                (
                    d["title"],
                    d.get("body", ""),
                    d.get("start_at"),
                    d.get("end_at"),
                    d.get("pinned", False),
                    nid,
                ),
            ).fetchone()
            audit(
                c,
                actor,
                "notice_edit",
                str(nid),
                {k: str(v) for k, v in before.items()},
                {k: str(v) for k, v in d.items()},
            )
    return row


def end_notice(actor: str | None, nid: int) -> bool:
    with connect() as c:
        r = c.execute(
            "update app.notices set end_at = now() where notice_id = %s returning notice_id", (nid,)
        ).fetchone()
        if r:
            audit(c, actor, "notice_end", str(nid))
    return r is not None


# ── 8 설정 ────────────────────────────────────────────


def rule_tables() -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            "select rule_key, valid_from, valid_to, value, basis, reviewed_at from ref.rule_tables order by rule_key, valid_from desc"
        ).fetchall()


def new_rule_version(actor: str | None, key: str, valid_from: date, value: Any, basis: str) -> bool:
    """기준표 새 버전: 지난 버전은 남기고 끝날을 (새 적용일 - 1)로 닫음. 새 버전은 「검토 전」."""
    with connect() as c:
        prev = c.execute(
            "select valid_from, value from ref.rule_tables where rule_key = %s and valid_from < %s order by valid_from desc limit 1",
            (key, valid_from),
        ).fetchone()
        if not prev:
            return False
        c.execute(
            "update ref.rule_tables set valid_to = %s where rule_key = %s and valid_from = %s",
            (valid_from - timedelta(days=1), key, prev["valid_from"]),
        )
        c.execute(
            """insert into ref.rule_tables (rule_key, valid_from, value, basis) values (%s,%s,%s,%s)
               on conflict (rule_key, valid_from) do update set value = excluded.value, basis = excluded.basis,
                 reviewed_at = null, reviewed_by = null""",
            (key, valid_from, Jsonb(value), basis),
        )
        audit(c, actor, "rule_version", f"{key}|{valid_from}", prev["value"], value, basis)
    return True


def rule_reviewed(actor: str | None, key: str, valid_from: date) -> bool:
    with connect() as c:
        r = c.execute(
            """update ref.rule_tables set reviewed_at = now(), reviewed_by = %s
               where rule_key = %s and valid_from = %s returning rule_key""",
            (actor, key, valid_from),
        ).fetchone()
        if r:
            audit(c, actor, "rule_reviewed", f"{key}|{valid_from}")
    return r is not None


def set_flag(actor: str | None, key: str, enabled: bool) -> dict[str, Any] | None:
    with connect() as c:
        b = c.execute(
            "select enabled from app.feature_flags where flag_key = %s", (key,)
        ).fetchone()
        if b is None:
            return None
        row = c.execute(
            "update app.feature_flags set enabled = %s, updated_at = now() where flag_key = %s returning flag_key, enabled, note, updated_at",
            (enabled, key),
        ).fetchone()
        audit(c, actor, "set_flag", key, {"enabled": b["enabled"]}, {"enabled": enabled})
    return row


def dong_alias() -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute("select * from ref.dong_alias order by sido, city, old_name").fetchall()


def add_dong_alias(actor: str | None, d: dict[str, Any]) -> None:
    with connect() as c:
        c.execute(
            """insert into ref.dong_alias (sido, city, old_name, new_name, changed_on) values (%s,%s,%s,%s,%s)
               on conflict do nothing""",
            (d["sido"], d["city"], d["old_name"], d["new_name"], d.get("changed_on")),
        )
        audit(
            c,
            actor,
            "dong_alias_add",
            f"{d['sido']} {d['city']} {d['old_name']}",
            None,
            {k: str(v) for k, v in d.items()},
        )


def admins() -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            """select a.user_id, u.email, a.role, a.added_at from app.admins a join auth.users u on u.id = a.user_id
               order by a.added_at"""
        ).fetchall()
    for r in rows:
        r["email"] = mask(r["email"])
    return rows


def add_admin(actor: str | None, email: str, role: str) -> str | None:
    """관리자 추가(이미 옥스에 가입한 이메일만)."""
    with connect() as c:
        u = c.execute(
            "select id from auth.users where lower(email) = lower(%s)", (email.strip(),)
        ).fetchone()
        if not u:
            return None
        c.execute(
            """insert into app.admins (user_id, role, added_by) values (%s,%s,%s)
               on conflict (user_id) do update set role = excluded.role""",
            (u["id"], role, actor),
        )
        audit(c, actor, "admin_add", str(u["id"]), None, {"role": role})
    return str(u["id"])


def remove_admin(actor: str | None, uid: str) -> str:
    """관리자 빼기. 대표(owner)가 한 명뿐이면 못 뺌."""
    with connect() as c:
        r = c.execute("select role from app.admins where user_id = %s", (uid,)).fetchone()
        if not r:
            return "none"
        if r["role"] == "owner":
            n = c.execute("select count(*) as n from app.admins where role = 'owner'").fetchone()
            if n and n["n"] <= 1:
                return "last_owner"
        c.execute("delete from app.admins where user_id = %s", (uid,))
        audit(c, actor, "admin_remove", uid, {"role": r["role"]})
    return "ok"


def audit_log(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            """select l.audit_id, l.at, l.action, l.target, l.before_val, l.after_val, l.note, u.email as actor
               from ops.audit_log l left join auth.users u on u.id = l.actor_id order by l.audit_id desc limit %s""",
            (limit,),
        ).fetchall()
    for r in rows:
        r["actor"] = mask(r["actor"]) if r["actor"] else "서버"
    return rows


# ── 7 통계(2단계 일부, 11/2) ─────────────────────────


def stats(days: int) -> dict[str, Any]:
    """주별 추이(최근 12주)와 많이 본 물건 10개(기간 안). 사용 기록은 이름 없이(anon_id)만."""
    with connect() as c:
        weeks = c.execute(
            """with w as (select generate_series(date_trunc('week', now()) - interval '11 weeks',
                                                 date_trunc('week', now()), interval '1 week')::date as wk)
               select w.wk,
                      count(distinct e.anon_id) as devices,
                      count(e.*) filter (where e.kind = 'item_view') as views,
                      count(distinct e.anon_id) filter (where e.kind = 'watch_add') as watched,
                      count(distinct e.anon_id) filter (where e.kind = 'calc') as calc,
                      (select count(*) from auth.users u
                        where u.created_at >= w.wk and u.created_at < w.wk + 7) as new_users
               from w left join app.events e on e.at >= w.wk and e.at < w.wk + 7
               group by w.wk order by w.wk"""
        ).fetchall()
        top = c.execute(
            """select e.item_id, count(*) as views, count(distinct e.anon_id) as devices,
                      coalesce(max(i.address), max(o.address), max(o.title)) as address, max(i.sale_date) as sale_date
               from app.events e left join core.items i using (item_id)
               left join core.onbid_items o on o.item_id = e.item_id
               where e.kind = 'item_view' and e.item_id is not null
                 and e.at > now() - make_interval(days => %s)
               group by e.item_id order by 2 desc limit 10""",
            (days,),
        ).fetchall()
    return {"weeks": weeks, "top": top}


# ── 물건 숨기기(11/2): display_policy 를 blocked 로(수집기는 이 칸을 다시 쓰지 않음) ──


def _item_table(item_id: str) -> str:
    return "core.onbid_items" if item_id.startswith("OB-") else "core.items"


def hide_item(actor: str | None, item_id: str, hidden: bool, reason: str | None) -> bool:
    tbl = _item_table(item_id)
    with connect() as c:
        b = c.execute(
            f"select display_policy::text as p from {tbl} where item_id = %s",  # noqa: S608 — 표 이름은 위 둘 중 하나
            (item_id,),
        ).fetchone()
        if not b:
            return False
        c.execute(
            f"update {tbl} set display_policy = %s where item_id = %s",  # noqa: S608
            ("blocked" if hidden else "public", item_id),
        )
        audit(
            c,
            actor,
            "item_hide" if hidden else "item_show",
            item_id,
            {"policy": b["p"]},
            None,
            reason,
        )
    return True


def hidden_items() -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            """select item_id, address, sale_date from core.items where display_policy = 'blocked'
               union all
               select item_id, null, null from core.onbid_items where display_policy = 'blocked'
               order by 1 limit 200"""
        ).fetchall()
