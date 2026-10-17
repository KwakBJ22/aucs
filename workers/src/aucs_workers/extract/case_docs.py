"""사건 서류 데이터 → core (사건 기본·문건 흐름). 분류는 원문으로, 화면용은 이름을 가립니다."""

from datetime import date, datetime
from typing import Any

import psycopg

from aucs_workers.extract.doc_events import classify, importance
from aucs_workers.extract.mask import mask_names


def _d(v: Any) -> date | None:
    try:
        return datetime.strptime(str(v)[:8], "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def case_basics(info: dict[str, Any]) -> dict[str, Any]:
    """사건내역 → 경매계·배당요구종기."""
    base = info.get("dma_csBasInf") or {}
    found = [_d(x.get("dstrtDemnLstprdYmd")) for x in info.get("dlt_dstrtDemnLstprdDts") or []]
    deadlines = [d for d in found if d is not None]
    return {
        "dept_name": base.get("cortAuctnJdbnNm"),
        "claim_deadline": max(deadlines) if deadlines else None,
    }


def case_events(deliveries: dict[str, Any], claim_deadline: date | None) -> list[dict[str, Any]]:
    """문건 접수·송달 내역 → 분류·중요도가 붙은 줄들."""
    rows: list[tuple[str, date | None, str]] = []
    for x in deliveries.get("dlt_ofdocDtsLst") or []:
        rows.append(("접수", _d(x.get("ofdocRcptYmd")), str(x.get("rcptDts") or "")))
    for x in deliveries.get("dlt_dlvrDtsLst") or []:
        rows.append(("송달", _d(x.get("dlvrbkRegYmd")), str(x.get("dlvrDts") or "")))
    out = []
    for kind, d, text in rows:
        cat = classify(text, kind)
        imp, late = importance(cat, d, claim_deadline)
        out.append({"event_date": d, "kind": kind, "category": cat, "importance": imp,
                    "after_deadline": late, "text_masked": mask_names(text), "text_raw": text})  # fmt: skip
    return out


def apply_case_docs(
    conn: psycopg.Connection, case_id: str, docs: dict[str, dict[str, Any]]
) -> None:
    """받은 서류로 사건 기본을 고치고 문건 흐름을 새로 씁니다(문건송달이 비어 오면 예전 것 유지)."""
    basics = case_basics(docs.get("case_info") or {})
    conn.execute(
        "update core.cases set dept_name = coalesce(%s, dept_name), claim_deadline = coalesce(%s, claim_deadline),"
        " updated_at = now() where case_id = %s",
        (basics["dept_name"], basics["claim_deadline"], case_id),
    )
    deliveries = docs.get("deliveries") or {}
    if not deliveries:
        return
    events = case_events(deliveries, basics["claim_deadline"])
    conn.execute("delete from core.case_events where case_id = %s", (case_id,))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into core.case_events (case_id, event_date, kind, category, importance, after_deadline,"
            " text_masked, text_raw, fetched_at) values (%s,%s,%s,%s,%s,%s,%s,%s, now())",
            [
                (
                    case_id,
                    e["event_date"],
                    e["kind"],
                    e["category"],
                    e["importance"],
                    e["after_deadline"],
                    e["text_masked"],
                    e["text_raw"],
                )
                for e in events
            ],  # fmt: skip
        )
