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


_CLAIM = re.compile(r"^\s*임차인\s*(\S)\S*\s.*배당요구")


def tenant_claim_dates(deliveries: dict[str, Any], names: list[str | None]) -> list[date | None]:
    """문건 접수 「임차인 임O 권리신고및배당요구신청 제출」 → 임차인별 배당요구일(가장 이른 날).

    법원이 이름을 가려 첫 글자로만 맞춥니다. 임차인이 한 명이면 첫 글자가 안 맞아도 그 사람으로 봅니다.
    같은 첫 글자 임차인이 둘 이상이면 누군지 몰라 비워 둡니다."""
    found: list[tuple[str, date]] = []
    for x in deliveries.get("dlt_ofdocDtsLst") or []:
        m = _CLAIM.search(str(x.get("rcptDts") or ""))
        d = _d(x.get("ofdocRcptYmd"))
        if m and d:
            found.append((m.group(1), d))
    out: list[date | None] = []
    for n in names:
        first = (n or "")[:1]
        same = [k for k in names if (k or "")[:1] == first]
        hits = [d for c, d in found if c == first] if first and len(same) == 1 else []
        if not hits and len(names) == 1:
            hits = [d for _, d in found]
        out.append(min(hits) if hits else None)
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
    if sched := docs.get("schedule"):
        apply_next_sales(conn, case_id, sched)  # 유찰된 물건의 다음 회차(11/4)
    deliveries = docs.get("deliveries") or {}
    if not deliveries:
        return
    # 임차인 배당요구일: 문건에서 (비어 있는 것만 채움)
    names = conn.execute(
        "select tenant_id, name_raw from core.tenants where case_id = %s order by tenant_id",
        (case_id,),
    ).fetchall()
    for (tid, _), d in zip(
        names, tenant_claim_dates(deliveries, [n for _, n in names]), strict=True
    ):
        if d:
            conn.execute(
                "update core.tenants set claim_date = %s where tenant_id = %s and claim_date is null",
                (d, tid),
            )
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


PREVIEW = "preview"  # 유찰 뒤 기일내역으로 미리 안 다음 회차(법원 공고 전, 11/4)


def next_sales(schedule: dict[str, Any], today: date) -> dict[int, dict[str, Any]]:
    """기일내역 → 물건 번호별 「아직 안 열린 다음 매각기일」·그 최저가·지금까지 유찰 횟수(순수 함수).

    유찰되면 법원이 그날 바로 다음 기일(보통 4~5주 뒤)과 낮아진 최저가를 잡아 둠 — 공고 목록보다 한 달쯤 먼저 알 수 있음.
    """
    out: dict[int, dict[str, Any]] = {}
    failed: dict[int, int] = {}
    for r in schedule.get("dlt_dxdyDtsLst") or []:
        if (r.get("auctnDxdyKndNm") or "") != "매각기일":
            continue
        seq = int(r.get("dspslGdsSeq") or 1)
        if (r.get("dxdyRslt") or "") == "유찰":
            failed[seq] = failed.get(seq, 0) + 1
            continue
        m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", str(r.get("dxdyTime") or ""))
        price = parse_krw(r.get("tsLwsDspslPrc"))
        if not m or r.get("dxdyRslt") or not price:
            continue
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d >= today and (seq not in out or d < out[seq]["date"]):
            out[seq] = {"date": d, "min_price_krw": price}
    for seq, x in out.items():
        x["failed_count"] = failed.get(seq, 0)
    return out


def past_failed_rounds(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    """기일내역 → 지난 유찰 회차들(순수 함수, 11/8). 물건 번호 · 날짜 · 그날 최저가 · 그 전 유찰 횟수.
    예전엔 우리가 목록을 처음 받은 뒤 회차만 쌓여 9번 유찰된 물건에 유찰이 1번만 있었음."""
    rows: dict[tuple[int, date], dict[str, Any]] = {}
    for r in schedule.get("dlt_dxdyDtsLst") or []:
        if (r.get("auctnDxdyKndNm") or "") != "매각기일" or (r.get("dxdyRslt") or "") != "유찰":
            continue
        m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", str(r.get("dxdyTime") or ""))
        if not m:
            continue
        seq = int(r.get("dspslGdsSeq") or 1)
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        rows[(seq, d)] = {"seq": seq, "date": d, "min_price_krw": parse_krw(r.get("tsLwsDspslPrc")),
                          "place": r.get("dxdyPlcNm")}  # fmt: skip
    out = sorted(rows.values(), key=lambda x: (x["seq"], x["date"]))
    n: dict[int, int] = {}
    for x in out:
        x["failed_before"] = n.get(x["seq"], 0)
        n[x["seq"]] = x["failed_before"] + 1
    return out


def apply_past_rounds(conn: psycopg.Connection, case_id: str, schedule: dict[str, Any]) -> int:
    """지난 유찰 회차를 core.rounds 에(있으면 결과만 「유찰」로). 우리 목록에 있는 물건만."""
    n = 0
    for x in past_failed_rounds(schedule):
        item_id = f"{case_id}-{x['seq']}"
        n += conn.execute(
            """insert into core.rounds (round_id, item_id, sale_date, appraisal_krw, min_price_krw,
                 failed_count, sale_place, result, fetched_at, checked_at)
               select %s, i.item_id, %s, i.appraisal_krw, %s, %s, %s, 'failed', now(), now()
               from core.items i where i.item_id = %s
               on conflict (round_id) do update set result = 'failed', checked_at = now(),
                 min_price_krw = coalesce(core.rounds.min_price_krw, excluded.min_price_krw)
               where core.rounds.result <> 'failed'""",
            (f"{item_id}-{x['date']:%Y%m%d}", x["date"], x["min_price_krw"], x["failed_before"],
             x["place"], item_id),
        ).rowcount  # fmt: skip
    return n


def detail_schedule(detail: dict[str, Any], seq: int) -> dict[str, Any]:
    """물건상세의 기일 목록(gdsDspslDxdyLst) → 기일내역 꼴(11/7 — 기일내역 요청을 따로 하지 않으려고, 순수 함수).

    종류 01 = 매각기일, 결과 002 = 유찰, 결과 없음 = 아직 안 열림. 다른 결과(매각 등)는 「기타」로 넣어 다음 기일로 보지 않음."""
    rows = []
    for r in (detail.get("dma_result") or {}).get("gdsDspslDxdyLst") or []:
        ymd = str(r.get("dxdyYmd") or "")
        if len(ymd) != 8:
            continue
        code = r.get("auctnDxdyRsltCd")
        rows.append({
            "auctnDxdyKndNm": "매각기일" if r.get("auctnDxdyKndCd") == "01" else "기타",
            "dspslGdsSeq": seq,
            "dxdyRslt": "" if not code else ("유찰" if code == "002" else "기타"),
            "dxdyTime": f"{ymd[:4]}.{ymd[4:6]}.{ymd[6:]}",
            "tsLwsDspslPrc": str(r.get("tsLwsDspslPrc") or ""),
            "dxdyPlcNm": r.get("dxdyPlcNm"),
        })  # fmt: skip
    return {"dlt_dxdyDtsLst": rows}


def apply_next_sales(conn: psycopg.Connection, case_id: str, schedule: dict[str, Any]) -> int:
    """지난 회차에 머물러 있는 물건(기일이 지남)에 다음 기일·최저가를 넣고 「공고 전」으로 표시."""
    n = 0
    for seq, x in next_sales(schedule, date.today()).items():
        n += conn.execute(
            """update core.items set sale_date = %s, min_price_krw = %s, failed_count = greatest(coalesce(failed_count, 0), %s),
                      status_code = %s, updated_at = now()
               where case_id = %s and item_no = %s and sale_date < current_date and sale_date < %s""",
            (x["date"], x["min_price_krw"], x["failed_count"], PREVIEW, case_id, seq, x["date"]),
        ).rowcount
    return n


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
