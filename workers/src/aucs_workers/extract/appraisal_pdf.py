"""감정평가서 원본(PDF) → 회사 이름 · 쪽수 · 앞부분 글 · 요항표 (11/4 — KAPA 허락, 화면엔 가린 요점만).

11/11: 요항표(「(1) 위치 및 주위환경 …」)도 읽어 법원 물건상세의 요항 목록(aeeWevlMnpntLst)과 같은 꼴로 남김
— 법원 요항을 아직 못 받은 물건도 「감정평가 요점」이 보이게.

PDF 자체는 저장하지 않음(한 건 수~수십 MB). 앞 몇 쪽 글만 raw 에 남겨 평가 근거 · 회사 이름을 다시 뽑을 수 있게.
"""

import io
import re
from collections import Counter
from typing import Any

HEAD_PAGES = 6
HEAD_CHARS = 8000

_FIRM = re.compile(
    r"((?:\(주\)|㈜|주식회사)?\s*[가-힣A-Za-z0-9]{1,20}"
    r"(?:감정평가법인|감정평가사\s*사무소|감정평가\s*사무소)(?:\s*(?:\(주\)|㈜))?)"
)
_NOT_FIRM = ("한국감정평가사협회", "협회")


def firm_name(text: str) -> str | None:
    """앞 쪽 글에서 가장 많이 나온 「○○감정평가법인 / ○○감정평가사사무소」."""
    found = []
    for m in _FIRM.finditer(text or ""):
        name = re.sub(r"\s+", "", m.group(1))
        name = name.replace("주식회사", "(주)").replace("㈜", "(주)")
        if any(w in name for w in _NOT_FIRM) or len(name) < 6:
            continue
        found.append(name)
    if not found:
        return None
    return Counter(found).most_common(1)[0][0]


# 요항표 제목 → 법원 요항 코드(aucs_rules.appraisal_points.LABELS 와 같은 코드). 긴 제목부터 — 먼저 맞는 것.
_TITLES: tuple[tuple[str, str], ...] = (
    ("토지이용계획 및 제한상태", "00083011"),
    ("토지의 형상 및 이용상태", "00083008"),
    ("형상 및 이용상태", "00083008"),
    ("형태 및 이용상태", "00083008"),
    ("위치 및 주위환경", "00083001"),
    ("교통상황", "00083003"),
    ("인접 도로상태", "00083004"),
    ("건물의 구조", "00083015"),
    ("이용상태", "00083006"),
    ("설비내역", "00083017"),
    ("제시목록 외의 물건", "00083013"),
    ("부합물 및 종물", "00083013"),
    ("공부와의 차이", "00083014"),
    ("기타 참고사항", "00083026"),
)


def _loose(title: str) -> str:
    """제목 글자 사이 띄어쓰기가 회사마다 달라 — 글자 사이 빈칸을 모두 허용하는 정규식 조각."""
    return r"\s*".join(re.escape(ch) for ch in title.replace(" ", ""))


_TITLE = "|".join(f"(?P<t{i}>{_loose(t)})" for i, (t, _) in enumerate(_TITLES))
_TAIL = r"(?:\s*등)?(?:\s*\(?\s*임대관계\s*및\s*기타\s*\)?)?"
# 제목 한 줄: 「(1) 위치 및 주위환경」「1. 위치 및 주위환경」「위치 및 주위환경1.」 모두
_HEADING = re.compile(
    rf"^\s*(?:\(\s*\d{{1,2}}\s*\)|\d{{1,2}}\s*[.)])?\s*(?:{_TITLE}){_TAIL}\s*(?:\d{{1,2}}\s*\.)?[\s()]*$"
)
# 한 줄에 제목이 여럿(맨 위 차례 줄) · 제목과 글이 붙어 나온 것을 줄로 가름
_CUT = re.compile(
    rf"(\(\s*\d{{1,2}}\s*\)\s*(?:{_loose('기타 참고사항')}{_TAIL}|"
    + "|".join(_loose(t) for t, _ in _TITLES if t != "기타 참고사항")
    + rf")(?:\s*등)?|(?:{'|'.join(_loose(t) for t, _ in _TITLES)}){_TAIL}\s*\d{{1,2}}\s*\.)"
)
_PAGE_NO = re.compile(r"^\s*(?:(?:Page|페이지|쪽)\s*[:：]?\s*\d+|-\s*\d+\s*-)\s*$", re.I)
CASE_NO = re.compile(r"(20\d\d)\s*타\s*경\s*(\d{1,7})")
# 「(2025타경59003)」이 글로 뽑힐 때 「타경(2025 59003)」으로 순서가 뒤바뀌는 PDF 가 있음(11/14 수원 2025타경59003 —
# 맞는 서류인데 사건번호를 못 읽어 바로 「안 맞음」이 됐음)
CASE_NO_SWAPPED = re.compile(r"타\s*경\s*\(?\s*(20\d\d)[\s-]+(\d{1,7})(?!\d)")


def _lines(page: str) -> list[str]:
    """한 쪽 글 → 줄. 한 글자씩 세로로 뽑힌 글은 이어 붙이고, 한 줄에 붙은 제목은 가름."""
    out: list[str] = []
    run: list[str] = []

    def close() -> None:
        if len(run) >= 3:
            out.append("".join(run))
        else:
            out.extend(run)
        run.clear()

    for ln in page.replace("\r", "").split("\n"):
        if len(ln) <= 1:
            run.append(ln or " ")
        else:
            close()
            out.append(ln)
    close()
    cut: list[str] = []
    for ln in out:
        cut.extend(_CUT.sub(lambda m: f"\n{m.group(1)}\n", ln).split("\n"))
    return [re.sub(r"[ \t]+", " ", ln).strip() for ln in cut]


def _title(line: str) -> int | None:
    """제목 줄이면 _TITLES 의 몇 번째인지, 아니면 None."""
    m = _HEADING.match(line)
    if not m:
        return None
    return next(i for i in range(len(_TITLES)) if m.group(f"t{i}"))


def _sheet(lines: list[str], repeat: set[str]) -> list[tuple[int | None, str]]:
    """요항표 한 쪽 → [(제목 번호, "") 또는 (None, 글 한 줄)]. 쪽 맨 위 차례(제목만 셋 넘게 이어진 것)는 뺌."""
    items: list[tuple[int | None, str]] = []
    for ln in lines:
        flat = re.sub(r"\s", "", ln)
        if not ln or ln in repeat or _PAGE_NO.match(ln) or "요항표" in flat[-12:]:
            continue
        if firm_name(ln) and len(flat) <= 24:  # 바닥의 회사 이름
            continue
        t = _title(ln)
        items.append((t, "") if t is not None else (None, ln))
    n = 0
    while n < len(items) and items[n][0] is not None:
        n += 1
    if n >= 3:
        # 차례 바로 뒤에 진짜 첫 제목이 붙어 있으면(차례에 이미 나온 제목) 그것은 남김
        keep = 1 if items[n - 1][0] in {t for t, _ in items[: n - 1]} else 0
        items = items[n - keep :]
    return items


def points_from_pages(pages: list[str]) -> list[dict[str, Any]]:
    """쪽마다 뽑은 글 → 요항 목록 [{aeeWevlMnpntItmCd, aeeWevlMnpntDtlSeq, aeeWevlMnpntCtt}] (요항표 쪽만 읽음)."""
    sheets = [_lines(p) for p in pages if "요항표" in re.sub(r"\s", "", p)]
    if not sheets:
        return []
    # 쪽마다 되풀이되는 머리·바닥 줄(감정서 번호 · 회사 이름)은 요항 글이 아님
    seen = Counter(ln for sh in sheets for ln in set(sh) if ln)
    need = max(
        2, (len(sheets) + 1) // 2
    )  # 번호 줄이 몇 쪽에서만 빠지는 회사가 있어, 숫자가 든 짧은 줄은 절반 넘으면 되풀이로 봄
    repeat = {
        ln
        for ln, n in seen.items()
        if _title(ln) is None
        and len(sheets) > 1
        and (n == len(sheets) or (n >= need and len(ln) <= 30 and re.search(r"\d", ln)))
    }
    out: list[dict[str, Any]] = []
    cur: str | None = None
    buf: list[str] = []

    def flush() -> None:
        text = " ".join(buf).strip()
        if cur and text:
            out.append(
                {
                    "aeeWevlMnpntItmCd": cur,
                    "aeeWevlMnpntDtlSeq": len(out) + 1,
                    "aeeWevlMnpntCtt": text,
                }
            )

    for sh in sheets:
        for t, text in _sheet(sh, repeat):
            if t is None:
                buf.append(text)
                continue
            flush()
            cur, buf = _TITLES[t][1], []
    flush()
    return out


def case_numbers(text: str) -> list[str]:
    """글 속 사건번호 「2025타경56683」들(띄어 쓴 것도)."""
    t = text or ""
    return list(
        dict.fromkeys(
            f"{y}타경{int(n)}" for y, n in CASE_NO.findall(t) + CASE_NO_SWAPPED.findall(t)
        )
    )


def has_report_no(text: str, report_no: str | None) -> bool:
    """글에 이 감정평가서 번호(법원 감정평가 정보의 aeeWevlNo, 「SR2511-01-012」)가 적혀 있는지.
    쪽마다 찍히는 번호라 사건번호가 깨져 뽑혀도 가를 수 있음. 너무 짧은 번호(여섯 글자 아래)는 안 씀."""
    no = re.sub(r"\s", "", report_no or "")
    return len(no) >= 6 and no in re.sub(r"\s", "", text or "")


def same_case(text: str, case_no: str) -> bool:
    """글자 인식한 글에 이 사건번호가 있는지(11/14). 「타경」이 깨져 읽혀도 연도 바로 뒤(글자 여섯 안)에
    같은 번호가 오면 맞다고 봄 — 번호가 다르면 안 맞음(틀리게 읽힌 숫자는 관리자 확인으로 남음)."""
    if case_no in case_numbers(text):
        return True
    year, _, num = case_no.partition("타경")
    flat = re.sub(r"[ \t]", "", text or "")
    return bool(year and num and re.search(rf"(?<!\d){year}\D{{1,6}}0*{num}(?!\d)", flat))


def read_pdf(data: bytes) -> dict[str, Any]:
    """PDF 바이트 → {firm, pages, bytes, scanned, head, points}. 글이 거의 없으면 그림으로 만든 PDF(scanned)."""
    from pypdf import PdfReader

    r = PdfReader(io.BytesIO(data))
    texts = []
    for pg in r.pages[:HEAD_PAGES]:
        try:
            # NUL 글자는 DB 가 못 받음(11/11 폴더 작업 실패)
            texts.append((pg.extract_text() or "").replace("\x00", ""))
        except Exception:  # noqa: BLE001 — 깨진 쪽은 건너뜀
            texts.append("")
    head = re.sub(r"[ \t]+", " ", "\n".join(texts)).strip()
    rest = []
    for pg in r.pages[HEAD_PAGES:]:
        try:
            rest.append((pg.extract_text() or "").replace("\x00", ""))
        except Exception:  # noqa: BLE001
            rest.append("")
    return {
        "points": points_from_pages(texts + rest),
        "firm": firm_name(head),
        "pages": len(r.pages),
        "bytes": len(data),
        "scanned": len(head) < 200,
        "head": head[:HEAD_CHARS],
    }
