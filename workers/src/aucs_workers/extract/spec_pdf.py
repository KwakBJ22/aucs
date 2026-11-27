"""관리자가 올린 매각물건명세서 PDF → 임차인 줄(11/27 대표님 — 법원에서 더는 못 받는 지난 물건).

법원 문서뷰어(court_spec)와 같은 꼴(쪽 → 글 조각 · 글자마다 rect)로 바꿔 extract.spec 으로 읽음.
글자 PDF 만 읽음(그림 PDF 는 글자가 없어 빈 결과). 좌표는 PDF 점 단위 · 위로 갈수록 큼(뷰어와 같음).
"""

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from aucs_workers.collectors.parse import checksum
from aucs_workers.extract.spec import parse_tenants, words_from_texts

MAX_PAGES = 30


def pages_from_pdf(data: bytes) -> dict[int, list[dict[str, Any]]]:
    """PDF 글자 → 쪽마다 줄 조각 {text, rect[{left, right, top}]}(글자 하나에 rect 하나)."""
    import ctypes

    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    ox, oy = ctypes.c_double(), ctypes.c_double()
    doc = pdfium.PdfDocument(data)
    out: dict[int, list[dict[str, Any]]] = {}
    try:
        for p in range(min(len(doc), MAX_PAGES)):
            tp = doc[p].get_textpage()
            segs: list[dict[str, Any]] = []
            text, rects, base = "", [], None
            for i in range(tp.count_chars()):
                ch = tp.get_text_range(i, 1)
                if ch in ("\r", "\n", "\x00", ""):
                    if text:
                        segs.append({"text": text, "rect": rects})
                    text, rects, base = "", [], None
                    continue
                if ch.isspace():  # 빈칸은 자리가 엉뚱할 때가 있어 앞 글자 오른쪽에 붙임(낱말 끊기만 함)
                    if text:
                        x = rects[-1]["right"]
                        text += " "
                        rects.append({"left": x, "right": x, "top": rects[-1]["top"]})
                    continue
                left, _b, right, _t = tp.get_charbox(i, loose=True)
                # 높이는 글자 기준선(글자 크기와 상관없이 한 줄이 같은 높이)
                raw.FPDFText_GetCharOrigin(tp.raw, i, ctypes.byref(ox), ctypes.byref(oy))
                top = oy.value
                # 줄이 바뀌면(높이가 3pt 넘게 다르거나 왼쪽으로 돌아가면) 새 조각
                if base is not None and (abs(top - base) > 3 or (rects and left < rects[-1]["left"] - 1)):
                    segs.append({"text": text, "rect": rects})
                    text, rects = "", []
                if not text:
                    base = top
                text += ch
                rects.append({"left": float(left), "right": float(right), "top": float(base if base is not None else top)})
            if text:
                segs.append({"text": text, "rect": rects})
            out[p] = segs
            tp.close()
    finally:
        doc.close()
    return out


def store_upload(
    conn: psycopg.Connection, item: dict[str, Any], data: bytes, file_name: str
) -> dict[str, Any]:
    """올린 PDF → raw 'spec_<물건번호>'(법원 원본과 같은 칸) + core.tenants(source='spec').
    item = {item_id, case_id, item_no, sale_date}. 현황조사서 임차인 줄은 court_spec 과 같이 지움(두 번 세지 않게).
    원본 PDF 는 글자가 없어도(그림 PDF) 보관함(court-docs)에 남김 — 나중에 글자 인식으로 읽을 수 있게."""
    from aucs_workers.doc_files import save_file

    pages = pages_from_pdf(data)
    kept = save_file(conn, item["case_id"], item["item_no"], "spec", "upload", data,
                     sale_date=item.get("sale_date"), pages=len(pages))  # fmt: skip
    words = words_from_texts(pages)
    payload = {"source": "upload", "file_name": file_name[:120], "pages": len(pages),
               "status": 200, "words": [list(w) for w in words]}  # fmt: skip
    if not words:
        return {"ok": False, "why": "no_text", "rows": 0, "kept": bool(kept.get("path"))}
    res = parse_tenants(words)
    conn.execute(
        "insert into raw.court_doc_raw (case_id, doc_kind, payload, checksum) values (%s,%s,%s,%s) on conflict do nothing",
        (item["case_id"], f"spec_{item['item_no']}", Jsonb(payload), checksum(payload)),
    )
    conn.execute("delete from core.tenants where item_id = %s and source = 'spec'", (item["item_id"],))
    for r in res["rows"]:
        name = r.get("name") or ""
        lease = "임차권" in (r.get("title") or "") + (r.get("source") or "")
        conn.execute(
            """insert into core.tenants (case_id, item_id, name_masked, name_raw, occupied_part, move_in_date, fixed_date,
                   claim_date, deposit_krw, monthly_rent_krw, has_lease_registration, source, fetched_at)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'spec', now())""",
            (item["case_id"], item["item_id"], (name[0] + "○○") if name else None, name or None, r.get("part"),
             r.get("move_in_date"), r.get("fixed_date"), r.get("claim_date"), r.get("deposit_krw"),
             r.get("monthly_rent_krw"), lease),
        )  # fmt: skip
    if res["rows"] or res["none"]:
        conn.execute(
            """delete from core.tenants t where t.case_id = %s and t.source = 'status_report'
               and (t.item_id = %s or (t.item_id is null and (select count(*) from core.items i
                    where i.case_id = t.case_id and i.status_code is distinct from 'gone') = 1))""",
            (item["case_id"], item["item_id"]),
        )
    conn.execute("update core.items set updated_at = now() where item_id = %s", (item["item_id"],))
    return {"ok": True, "rows": len(res["rows"]), "none": bool(res["none"]), "pages": len(pages),
            "kept": bool(kept.get("path"))}  # fmt: skip
