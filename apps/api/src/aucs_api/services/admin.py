"""관리자 화면(ADM-01)용 조합: 수집 상태·검증 대기·공개 설정·기준표."""

from typing import Any

from aucs_api.db import connect


def status() -> dict[str, Any]:
    with connect() as c:
        jobs = c.execute(
            """select distinct on (r.job_id) r.job_id, j.name_ko, r.started_at, r.finished_at, r.status,
                      r.item_count, left(r.message, 200) as message
               from ops.job_runs r join ops.jobs j using (job_id)
               order by r.job_id, r.started_at desc"""
        ).fetchall()
        counts = c.execute(
            """select (select count(*) from core.items where sale_date >= current_date) as items_upcoming,
                      (select count(*) from core.items i where sale_date >= current_date
                         and not exists (select 1 from analysis.item_analysis x where x.item_id = i.item_id)) as items_pending,
                      (select count(*) from core.sale_results) as sale_results,
                      (select count(*) from core.trades) as trades,
                      (select count(distinct case_id) from raw.court_doc_raw) as cases_with_docs,
                      pg_database_size(current_database()) as db_bytes"""
        ).fetchone()
    return {
        "jobs": jobs,
        "counts": counts,
        "db_limit_bytes": 8 * 1024 * 1024 * 1024,
        "metrics": metrics(),
    }


_METRICS_SQL = """
with w as (select * from app.events where at >= now() - interval '7 days'),
first_seen as (select anon_id, min(at) as t0 from app.events group by 1),
first_item as (select anon_id, min(at) as t1 from app.events where kind = 'item_view' group by 1)
select
  (select count(distinct anon_id) from w) as devices,
  (select count(distinct anon_id) from w where kind = 'start_done') as started,
  (select count(distinct anon_id) from w where kind = 'item_view') as viewed,
  (select count(distinct anon_id) from w where kind = 'watch_add') as watched,
  (select count(distinct anon_id) from w where kind = 'calc') as calc,
  (select percentile_cont(0.5) within group (order by extract(epoch from fi.t1 - fs.t0))
     from first_seen fs join first_item fi using (anon_id) where fs.t0 >= now() - interval '7 days') as first_item_sec,
  (select count(*) from first_seen where t0 between now() - interval '14 days' and now() - interval '7 days') as cohort,
  (select count(distinct w.anon_id) from w join first_seen fs using (anon_id)
     where fs.t0 between now() - interval '14 days' and now() - interval '7 days') as returned
"""


def metrics() -> dict[str, Any]:
    """사용 기록 7일(성공 지표): 기기 수, 시작·상세·관심·계산까지 간 기기, 처음 들어와 첫 상세까지 걸린 시간, 주간 재방문."""
    with connect() as c:
        m = dict(c.execute(_METRICS_SQL).fetchone() or {})
    sec = m.get("first_item_sec")
    m["first_item_sec"] = round(float(sec)) if sec is not None else None
    return m


def review_queue(limit: int = 50) -> dict[str, Any]:
    with connect() as c:
        fields = c.execute(
            """select f.field_id, d.case_id, d.doc_kind, f.field, f.raw_text, f.confidence
               from core.extracted_fields f join core.documents d using (doc_id)
               where f.check_status = 'needs_review' order by f.field_id limit %s""",
            (limit,),
        ).fetchall()
        signals = c.execute(
            """select s.item_id, s.rule_id, s.level, s.title, i.sale_date
               from analysis.risk_signals s join core.items i using (item_id)
               where s.status = '확인 필요' and i.sale_date >= current_date
               order by i.sale_date, s.item_id limit %s""",
            (limit,),
        ).fetchall()
        reports = c.execute(
            """select r.report_id, r.item_id, r.section, r.note, r.created_at::date::text as at
               from app.value_reports r where r.status = 'open' order by r.created_at desc limit %s""",
            (limit,),
        ).fetchall()
    return {"fields": fields, "signals": signals, "reports": reports}


REPORT_REPLY = {
    "fixed": ("제보하신 값을 고쳤어요", "알려 주셔서 고맙습니다 · 물건 화면에서 확인해 보세요"),
    "rejected": ("제보하신 값을 확인했어요", "원문과 대조해 보니 지금 값이 맞아 그대로 두었어요"),
}


def close_report(report_id: int, status: str) -> bool:
    """「틀렸어요」 제보 처리: 고침(fixed)·안 고침(rejected). 제보한 사람에게 알림 한 통."""
    title, body = REPORT_REPLY[status]
    with connect() as c:
        r = c.execute(
            """update app.value_reports set status = %s, closed_at = now()
               where report_id = %s and status = 'open' returning user_id, item_id""",
            (status, report_id),
        ).fetchone()
        if not r:
            return False
        c.execute(
            "insert into app.notifications (user_id, title, body, link) values (%s, %s, %s, %s)",
            (r["user_id"], title, body, f"/item/{r['item_id']}"),
        )
    return True


def flags() -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            "select flag_key, enabled, note, updated_at from app.feature_flags order by flag_key"
        ).fetchall()


def set_flag(key: str, enabled: bool) -> dict[str, Any] | None:
    with connect() as c:
        before = c.execute(
            "select enabled from app.feature_flags where flag_key = %s", (key,)
        ).fetchone()
        if before is None:
            return None
        row = c.execute(
            "update app.feature_flags set enabled = %s, updated_at = now() where flag_key = %s returning flag_key, enabled, note, updated_at",
            (enabled, key),
        ).fetchone()
        c.execute(
            "insert into ops.audit_log (action, target, before_val, after_val) values ('set_flag', %s, %s::jsonb, %s::jsonb)",
            (
                key,
                f'{{"enabled": {str(before["enabled"]).lower()}}}',
                f'{{"enabled": {str(enabled).lower()}}}',
            ),
        )
        return row


def rule_tables() -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            "select rule_key, valid_from, valid_to, value, basis from ref.rule_tables order by rule_key, valid_from"
        ).fetchall()
