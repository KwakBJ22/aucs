"""관리자 「명세서 올리기」(11/27 대표님): 법원에서 더는 못 받는 지난 물건의 매각물건명세서 PDF 를 찾아 올림.

목록 = 매각기일이 지난 수도권 물건 중 명세서 원본(법원 뷰어 · 올린 PDF)이 없는 것, 최근 기일 순.
올린 PDF 는 바로 읽어 임차인 줄(core.tenants source='spec')로 넣음 — 법원 원본과 같은 칸(raw 'spec_<물건번호>').
"""

from typing import Any

from aucs_rules.courts import COURTS

from aucs_api.db import connect

MAX_BYTES = 10 * 1024 * 1024
PAGE = 50
_SPEC = """left join lateral (select r.payload->>'source' as src, r.fetched_at
             from raw.court_doc_raw r where r.case_id = i.case_id and r.doc_kind = 'spec_' || i.item_no
               and coalesce((r.payload->>'pages')::int, 0) > 0
             order by r.fetched_at desc limit 1) s on true"""
_COLS = """i.item_id, c.court_code, c.case_no, i.item_no, i.address, i.usage_name, i.sale_date,
           s.src, s.fetched_at as spec_at,
           (select count(*) from core.tenants t where t.item_id = i.item_id and t.source = 'spec') as spec_rows"""
_PAST = "i.sale_date < current_date and i.sido in ('서울특별시', '경기도', '인천광역시')"


def spec_items(q: str, offset: int = 0) -> dict[str, Any]:
    """q 가 있으면 사건번호로(지난 · 진행 모두), 없으면 지난 물건 중 명세서 없는 것."""
    from aucs_api.services.items import parse_query

    with connect() as c:
        if q.strip():
            pq = parse_query(q)
            if not pq or pq["kind"] == "text":
                return {"rows": [], "total": 0}
            v = pq["case_no"] if pq["kind"] == "case" else "%" + pq["suffix"]
            rows = c.execute(
                f"""select {_COLS} from core.items i join core.cases c using (case_id) {_SPEC}
                    where c.case_no like %s order by i.sale_date desc nulls last, c.court_code, i.item_no limit 30""",
                (v,),
            ).fetchall()
            total = len(rows)
        else:
            rows = c.execute(
                f"""select {_COLS} from core.items i join core.cases c using (case_id) {_SPEC}
                    where {_PAST} and s.src is null
                    order by i.sale_date desc, c.court_code, c.case_no, i.item_no limit %s offset %s""",
                (PAGE, max(0, offset)),
            ).fetchall()
            total = c.execute(
                f"""select count(*) n from core.items i where {_PAST} and not exists (
                      select 1 from raw.court_doc_raw r where r.case_id = i.case_id and r.doc_kind = 'spec_' || i.item_no
                        and coalesce((r.payload->>'pages')::int, 0) > 0)"""
            ).fetchone()["n"]
    return {
        "total": int(total),
        "rows": [
            {
                "item_id": r["item_id"],
                "court": COURTS.get(r["court_code"], r["court_code"]),
                "case_no": r["case_no"],
                "item_no": r["item_no"],
                "address": r["address"],
                "usage": r["usage_name"],
                "sale_date": r["sale_date"].isoformat() if r["sale_date"] else None,
                # 명세서: court = 법원 뷰어에서 받음 · upload = 올린 PDF · None = 없음
                "spec": ("upload" if r["src"] == "upload" else "court") if r["spec_at"] else None,
                "spec_rows": int(r["spec_rows"] or 0),
            }
            for r in rows
        ],
    }


def save_spec(item_id: str, data: bytes, file_name: str) -> dict[str, Any]:
    """올린 PDF → 임차인 줄. 글자 없는 그림 PDF 면 ok=False."""
    from aucs_workers.extract.spec_pdf import store_upload

    with connect() as c:
        it = c.execute(
            "select item_id, case_id, item_no, sale_date from core.items where item_id = %s", (item_id,)
        ).fetchone()
        if not it:
            raise LookupError("물건을 찾지 못했어요")
        out = store_upload(c, dict(it), data, file_name)
    return out
