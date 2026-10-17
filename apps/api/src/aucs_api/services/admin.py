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
                      (select count(*) from core.sale_results) as sale_results,
                      (select count(*) from core.trades) as trades,
                      (select count(distinct case_id) from raw.court_doc_raw) as cases_with_docs,
                      pg_database_size(current_database()) as db_bytes"""
        ).fetchone()
    return {"jobs": jobs, "counts": counts, "db_limit_bytes": 500 * 1024 * 1024}


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
    return {"fields": fields, "signals": signals}


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
