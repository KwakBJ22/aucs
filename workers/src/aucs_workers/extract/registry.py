"""등기부(등기사항전부증명서) PDF → 권리 목록 → 규칙(aucs_rules.rights)으로 판정.

읽는 법 (지금 시스템 collectors/registry.py 에서 옮김)
- 글자가 있는 PDF: 「주요 등기사항 요약」이 있으면 그것(말소된 등기 빠져 있음), 없으면 갑구·을구 전체에서
  「N번…말소」 등기로 지워진 순위를 뺌 [검증 필요]
- 그림 PDF(인터넷등기소 열람용): registry_ocr 로 표 칸마다 글자 인식, 빨간 줄 그어진 글은 지우고 읽음

등기부는 회원이 올린 PDF 만 씁니다(인터넷등기소 직접 자동화 안 함).
"""

import re
from datetime import date
from pathlib import Path
from typing import Any

from aucs_rules.rights import Right

DATE_RE = r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"
AMOUNT_RE = re.compile(
    r"(채권최고액|전세금|임차보증금|보증금|청구금액|채권액)\s*금?\s*([\d,]{4,})\s*원"
)
HOLDER_RE = re.compile(
    r"(근저당권자|저당권자|채권자|권리자|전세권자|임차권자|가등기권자|수탁자|지상권자|지역권자)\s+"
    r"((?:주식회사\s*)?[가-힣A-Za-z0-9()]+(?:\s*주식회사)?)"
)
MOVE_IN_RE = re.compile(r"(?:주민등록일자|사업자등록신청일자)\s*(" + DATE_RE + ")")


def fix_date(text: str | None, today: date | None = None) -> date | None:
    """글자 인식 오타(18월·3023년 등)를 고쳐 가장 그럴듯한 날짜 하나."""
    today = today or date.today()
    for y, mo, d in re.findall(DATE_RE, text or ""):
        for yy in dict.fromkeys([y, "2" + y[1:], "1" + y[1:]]):
            for mm in dict.fromkeys([mo, mo.replace("8", "2"), mo.replace("3", "2"), mo[-1:]]):
                for dd in dict.fromkeys([d, d.replace("8", "2"), d.replace("3", "2")]):
                    try:
                        dt = date(int(yy), int(mm), int(dd))
                    except ValueError:
                        continue
                    if date(1950, 1, 1) <= dt <= today:
                        return dt
    return None


def _tidy(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_※*%]+", " ", t or "")).strip()


def ocr_to_rights(rows: list[dict[str, Any]], today: date | None = None) -> list[Right]:
    """글자 인식 결과 줄들 → Right. 부기등기의 금액 변경·권리자 이전은 주등기에 반영."""
    out: list[dict[str, Any]] = []
    for r in rows:
        body = _tidy(r.get("권리자및기타", ""))
        amt = AMOUNT_RE.search(body)
        hold = HOLDER_RE.findall(body)
        no = re.search(r"제\s*([\d,]+)\s*호", r.get("접수") or "")
        moved = MOVE_IN_RE.search(body)
        out.append({
            "section": r["구분"], "rank_no": r["순위번호"], "purpose": re.sub(r"\s+", "", r.get("등기목적") or ""),
            "receipt_date": fix_date(r.get("접수"), today) or fix_date(r.get("등기원인"), today),
            "receipt_no": int(no.group(1).replace(",", "")) if no else None,
            "amount_krw": int(amt.group(2).replace(",", "")) if amt else None,
            "holder": " ".join(h[1] for h in hold[:2]) if hold else "",
            "move_in_date": fix_date(moved.group(1), today) if moved else None,
            "source": {"page": r.get("쪽"), "struck_lines": r.get("지운줄수", 0), "method": "ocr"},
        })  # fmt: skip
    _merge_subordinates(out)
    return [Right(**{k: v for k, v in x.items()}) for x in out]


def _merge_subordinates(rows: list[dict[str, Any]]) -> None:
    """부기: 근저당권이전 → 권리자 바꿈, 변경 → 금액 바꿈."""
    main = {(r["section"], r["rank_no"]): r for r in rows if "-" not in (r["rank_no"] or "")}
    for r in rows:
        rk = r["rank_no"] or ""
        if "-" not in rk:
            continue
        m = main.get((r["section"], rk.split("-")[0]))
        if m is None:
            continue
        if "이전" in r["purpose"] and r["holder"]:
            m["holder"] = r["holder"]
        if "변경" in r["purpose"] and r["amount_krw"]:
            m["amount_krw"] = r["amount_krw"]


def read_pdf(path: Path) -> tuple[list[Right], dict[str, Any]]:
    """PDF 하나 읽기: 글자가 있으면 글자로, 없으면 글자 인식."""
    from pypdf import PdfReader

    text = "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    if len(re.sub(r"\s", "", text)) > 200 and re.search(r"갑\s*구|을\s*구|주요\s*등기사항", text):
        return text_to_rights(text), {"method": "text"}
    from aucs_workers.extract.registry_ocr import ocr_rows

    rows, head = ocr_rows(path)
    return ocr_to_rights(rows), {"method": "ocr", **head}


# ── 글자가 있는 PDF ─────────────────────────────────────────
_PURPOSES = [
    "소유권이전청구권가등기", "소유권이전담보가등기", "담보가등기", "가등기", "소유권보존", "소유권이전", "소유권일부이전",
    "근저당권설정", "근저당권이전", "근저당권변경", "저당권설정", "전세권설정", "전세권이전", "전세권변경",
    "주택임차권", "상가건물임차권", "임차권설정", "임차권", "구분지상권설정", "지상권설정", "지역권설정",
    "강제경매개시결정", "임의경매개시결정", "가압류", "압류", "가처분", "예고등기", "환매특약", "신탁",
]  # fmt: skip
_PURPOSE_RE = "|".join(sorted(_PURPOSES, key=len, reverse=True))
_ENTRY_RE = re.compile(
    rf"(?<![\d-])(?P<rank>\d{{1,3}}(?:-\d{{1,2}})?)\s+"
    rf"(?P<purpose>(?:\d+(?:-\d+)?번\s*)?(?:{_PURPOSE_RE})[가-힣()]*?(?:등기말소|말소|변경|경정)?)\s*"
    rf"(?P<date>{DATE_RE})\s*(?:제\s*(?P<no>[\d,]+)\s*호)?"
)


def _section(text: str, start: str, ends: list[str]) -> str:
    m = re.search(start, text)
    if not m:
        return ""
    rest = text[m.end() :]
    cut = [e.start() for p in ends if (e := re.search(p, rest))]
    return rest[: min(cut)] if cut else rest


def _entries(block: str, gu: str) -> list[dict[str, Any]]:
    flat = re.sub(r"\s*\n\s*", " ", block)
    ms = list(_ENTRY_RE.finditer(flat))
    out = []
    for i, m in enumerate(ms):
        body = flat[m.end() : ms[i + 1].start() if i + 1 < len(ms) else len(flat)]
        out.append({"구분": gu, "순위번호": m.group("rank"), "등기목적": m.group("purpose"),
                    "접수": m.group(0)[m.start("date") - m.start():], "등기원인": "", "권리자및기타": body})  # fmt: skip
    return out


def text_to_rights(text: str) -> list[Right]:
    t = re.sub(r"[ \t　]+", " ", re.sub(r"열람일시\s*:.*", " ", text))
    summ = _section(
        t, r"주요\s*등기사항\s*요약", [r"\[\s*참\s*고\s*사\s*항\s*\]", r"이\s*하\s*여\s*백"]
    )
    if summ:
        gap = _section(
            summ, r"2\.\s*소유지분을\s*제외한\s*소유권에\s*관한\s*사항", [r"3\.\s*\(근\)저당권"]
        )
        eul = _section(summ, r"3\.\s*\(근\)저당권\s*및\s*전세권\s*등", [])
        return ocr_to_rights(_entries(gap, "갑") + _entries(eul, "을"))
    gap = _section(t, r"【\s*갑\s*구\s*】", [r"【\s*을\s*구\s*】", r"주요\s*등기사항"])
    eul = _section(t, r"【\s*을\s*구\s*】", [r"주요\s*등기사항", r"이\s*하\s*여\s*백"])
    rows = _entries(gap, "갑") + _entries(eul, "을")
    gone = {
        (r["구분"], ref)
        for r in rows
        if "말소" in r["등기목적"]
        for ref in re.findall(r"(\d+(?:-\d+)?)번", r["등기목적"])
    }
    rows = [
        r for r in rows if (r["구분"], r["순위번호"]) not in gone and "말소" not in r["등기목적"]
    ]
    return ocr_to_rights(rows)


def save_rights(conn: Any, case_id: str, rights: list[Right]) -> int:
    """사건의 등기부 권리를 새로 씁니다(권리자 원문은 내부용 칸, 화면용은 가림)."""
    from aucs_rules.rights import analyze

    from aucs_workers.extract.mask import mask_names

    res = analyze(rights)
    base = res["base"].value
    doc_id = f"{case_id}-registry-{date.today():%Y%m%d}"
    conn.execute(
        "insert into core.documents (doc_id, case_id, doc_kind, fetched_at, display_policy) values (%s,%s,'registry', now(),'owner_only')"
        " on conflict (doc_id) do nothing",
        (doc_id, case_id),
    )
    conn.execute("delete from core.rights where case_id = %s", (case_id,))
    for r, j in res["rights"]:
        conn.execute(
            "insert into core.rights (case_id, section, rank_no, purpose, right_kind, receipt_date, receipt_no, amount_krw,"
            " holder_masked, holder_raw, is_base_right, fetched_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())",
            (
                case_id,
                r.section,
                r.rank_no,
                r.purpose,
                j.value,
                r.receipt_date,
                r.receipt_no,
                r.amount_krw,
                mask_names("권리자 " + r.holder).removeprefix("권리자 ") if r.holder else None,
                r.holder or None,
                r is base,
            ),  # fmt: skip
        )
    return len(rights)


def main() -> None:
    """회원이 올린(또는 받아 둔) 등기부 PDF 하나를 읽어 사건 권리로 넣습니다.

    uv run python -m aucs_workers.extract.registry --case B000250 2025타경55580 --file 등기부.pdf
    """
    import argparse

    from aucs_workers.db import connect

    ap = argparse.ArgumentParser()
    ap.add_argument("--case", nargs=2, required=True, metavar=("법원코드", "사건번호"))
    ap.add_argument("--file", required=True)
    a = ap.parse_args()
    rights, meta = read_pdf(Path(a.file))
    case_id = f"{a.case[0]}-{a.case[1]}"
    with connect() as conn:
        conn.execute(
            "insert into core.cases (case_id, court_code, case_no) values (%s,%s,%s) on conflict do nothing",
            (case_id, *a.case),
        )
        n = save_rights(conn, case_id, rights)
        conn.commit()
    print(f"{case_id}: 권리 {n}줄 ({meta['method']})")


if __name__ == "__main__":
    main()
