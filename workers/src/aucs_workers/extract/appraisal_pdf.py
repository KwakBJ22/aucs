"""감정평가서 원본(PDF) → 회사 이름 · 쪽수 · 앞부분 글 (11/4 — KAPA 허락, 화면엔 가린 요점만).

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


def read_pdf(data: bytes) -> dict[str, Any]:
    """PDF 바이트 → {firm, pages, bytes, scanned, head}. 글이 거의 없으면 그림으로 만든 PDF(scanned)."""
    from pypdf import PdfReader

    r = PdfReader(io.BytesIO(data))
    texts = []
    for pg in r.pages[:HEAD_PAGES]:
        try:
            texts.append(pg.extract_text() or "")
        except Exception:  # noqa: BLE001 — 깨진 쪽은 건너뜀
            texts.append("")
    head = re.sub(r"[ \t]+", " ", "\n".join(texts)).strip()
    return {
        "firm": firm_name(head),
        "pages": len(r.pages),
        "bytes": len(data),
        "scanned": len(head) < 200,
        "head": head[:HEAD_CHARS],
    }
