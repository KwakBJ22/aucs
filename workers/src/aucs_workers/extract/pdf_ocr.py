"""그림 PDF 앞쪽 몇 장을 글자로(11/14 — 손님이 올린 그림 감정평가서의 사건번호 확인).

등기부 글자 인식(registry_ocr)과 같은 tesseract · tessdata 를 씀. PC 에서만 돎(Vercel 에는 tesseract 가 없음).
"""

import os
import subprocess
import tempfile
from pathlib import Path

from aucs_workers.extract.registry_ocr import tessdata_dir, tesseract_cmd

DPI = 200
PAGES = 3


def ocr_head(data: bytes, pages: int = PAGES) -> str:
    """PDF 바이트 → 앞 pages 쪽의 글(쪽마다 줄바꿈). 못 읽은 쪽은 빈 글."""
    import pypdfium2 as pdfium

    cmd = tesseract_cmd()
    env = dict(os.environ)
    if d := tessdata_dir():
        env["TESSDATA_PREFIX"] = d
    doc = pdfium.PdfDocument(data)
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(min(pages, len(doc))):
            p = Path(tmp) / f"p{i}.png"
            doc[i].render(scale=DPI / 72).to_pil().convert("L").save(p)
            r = subprocess.run([cmd, str(p), "-", "-l", "kor", "--psm", "6"],
                               capture_output=True, env=env, timeout=120)  # fmt: skip
            out.append(r.stdout.decode("utf-8", "replace"))
    return "\n".join(out)
