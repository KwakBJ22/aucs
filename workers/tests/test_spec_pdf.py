"""올린 명세서 PDF 읽기(11/27): 뷰어 글 조각 픽스처로 PDF 를 만들어 다시 읽으면 같은 임차인 줄이 나와야 함."""

import io
import json
from pathlib import Path

import pytest
from aucs_workers.extract.spec import parse_tenants, words_from_texts
from aucs_workers.extract.spec_pdf import pages_from_pdf

FX = Path(__file__).parent / "fixtures"


def _pdf(ws: list[tuple]) -> bytes:
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    for p in sorted({w[0] for w in ws}):
        for pp, y, x0, x1, t in ws:
            if pp == p:
                c.setFont("HYSMyeongJo-Medium", max(4, min(9, (x1 - x0) / max(1, len(t)))))
                c.drawString(x0, y, t)
        c.showPage()
    c.save()
    return buf.getvalue()


@pytest.mark.parametrize("name", ["spec_words_51836", "spec_words_100740"])
def test_pdf_same_as_viewer(name: str) -> None:
    pytest.importorskip("pypdfium2")
    ws = [tuple(w) for w in json.loads((FX / f"{name}.json").read_text(encoding="utf-8"))]
    key = lambda r: (r.get("name"), r.get("deposit_krw"), r.get("move_in_date"), r.get("fixed_date"), r.get("claim_date"))  # noqa: E731
    a = [key(r) for r in parse_tenants(ws)["rows"]]
    b = [key(r) for r in parse_tenants(words_from_texts(pages_from_pdf(_pdf(ws))))["rows"]]
    assert a and a == b
