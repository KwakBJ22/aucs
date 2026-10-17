"""사건 서류 데이터 → core (사건 기본·문건 흐름). 분류는 원문으로, 화면용은 이름을 가립니다."""

import re
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
    if sr := docs.get("status_report"):
        if sr.get("dlt_ordTsLserLtn") is not None or sr.get("dlt_ordTsRlet"):
            save_tenants(conn, case_id, sr)
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


def parse_krw(text: Any) -> int | None:
    """「150,000,000」「150,000,000원」「500만 원」「1억2,000만원」 → 원. 「미상」「없음」 → None/0."""
    t = str(text or "").replace(" ", "").replace("원", "")
    if t in ("", "None", "미상"):
        return None
    if t == "없음":
        return 0
    m = re.fullmatch(r"(?:(\d[\d,]*)억)?(?:(\d[\d,]*)만)?(\d[\d,]*)?", t)
    if not m or not any(m.groups()):
        return None
    eok, man, rest = (int(g.replace(",", "")) if g else 0 for g in m.groups())
    return eok * 100_000_000 + man * 10_000 + rest


def parse_dot_date(text: Any) -> date | None:
    """「2025.05.15.」「2025.05.15.(전입세대확인서)」 → 날짜. 「미전입」「미상」 → None."""
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", str(text or ""))
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def tenants_from_status_report(sr: dict[str, Any]) -> list[dict[str, Any]]:
    """현황조사서 임대차관계 → 임차인 줄들 (원문 이름은 내부용 칸에만)."""
    out = []
    for x in sr.get("dlt_ordTsLserLtn") or []:
        name = str(x.get("intrpsNm") or "")
        out.append({
            "name_raw": name or None,
            "name_masked": (name[0] + "○○") if name else None,
            "occupied_part": None if str(x.get("lesPartCtt")) in ("None", "미상") else x.get("lesPartCtt"),
            "move_in_date": parse_dot_date(x.get("mvinDtlCtt")),
            "fixed_date": parse_dot_date(x.get("rgstryCrtcpCfmtnCtt")),
            "deposit_krw": parse_krw(x.get("lesDposDts")),
            "monthly_rent_krw": parse_krw(x.get("mmrntAmtDts")),
        })  # fmt: skip
    return out


def occupant_unknown(sr: dict[str, Any]) -> bool:
    """현황조사 점유관계에 「폐문부재」「아무도 만나지 못」 → 점유자 미상."""
    text = " ".join(str(x.get("gdsPossCtt") or "") for x in sr.get("dlt_ordTsRlet") or [])
    return bool(re.search(r"폐문부재|아무도 만나지 못|점유자\s*미상", text))


def save_tenants(conn: psycopg.Connection, case_id: str, sr: dict[str, Any]) -> int:
    rows = tenants_from_status_report(sr)
    conn.execute(
        "delete from core.tenants where case_id = %s and source = 'status_report'", (case_id,)
    )
    with conn.cursor() as cur:
        cur.executemany(
            "insert into core.tenants (case_id, name_masked, name_raw, occupied_part, move_in_date, fixed_date,"
            " deposit_krw, monthly_rent_krw, source, fetched_at) values (%s,%s,%s,%s,%s,%s,%s,%s,'status_report', now())",
            [
                (
                    case_id,
                    t["name_masked"],
                    t["name_raw"],
                    t["occupied_part"],
                    t["move_in_date"],
                    t["fixed_date"],
                    t["deposit_krw"],
                    t["monthly_rent_krw"],
                )
                for t in rows
            ],  # fmt: skip
        )
    return len(rows)
