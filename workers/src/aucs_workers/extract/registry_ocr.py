"""
등기부 PDF 가 글자 없이 그림으로만 된 경우(인터넷등기소 열람용) → 표 칸을 찾아 칸마다 글자 인식(OCR)

- 쪽을 300dpi 그림으로 → 검은 가로·세로 줄로 표 칸을 찾는다 → 칸마다 tesseract(한국어)로 읽는다
- 빨간 줄(말소·변경된 글자)이 그어진 줄은 지우고 읽는다 → 지금 유효한 글자만 남는다
- 결과: [{구분: 갑/을, 순위번호, 등기목적, 접수, 등기원인, 권리자및기타, 지운줄수}]

필요한 것: tesseract (Windows: winget install UB-Mannheim.TesseractOCR),
한국어 글자 자료 kor.traineddata (TESSDATA_PREFIX 또는 D:\\Auction\\system\\tessdata).
지금 시스템(collectors/registry_ocr.py)에서 그대로 옮겼습니다.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[4]
DPI = 300


def tesseract_cmd() -> str:
    for c in (
        os.environ.get("TESSERACT"),
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if c and Path(c).exists() or (c and shutil.which(c)):
            return c
    raise RuntimeError("tesseract 가 없습니다. PowerShell: winget install UB-Mannheim.TesseractOCR")


def tessdata_dir() -> str | None:
    for d in (
        os.environ.get("TESSDATA_PREFIX"),
        str(REPO / "tessdata"),
        str(REPO.parent / "system" / "tessdata"),
        str(Path.home() / "tess"),
    ):
        if d and (Path(d) / "kor.traineddata").exists():
            return d
    return None


def render(pdf: Path) -> list[Image.Image]:
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(pdf))
        return [doc[i].render(scale=DPI / 72).to_pil().convert("RGB") for i in range(len(doc))]
    except ImportError:
        tmp = Path(tempfile.mkdtemp())
        subprocess.run(["pdftoppm", "-r", str(DPI), "-png", str(pdf), str(tmp / "p")], check=True)
        return [Image.open(p).convert("RGB") for p in sorted(tmp.glob("p-*.png"))]


def runs(mask_1d: np.ndarray, min_gap: int = 3) -> list[tuple[int, int]]:
    """True 가 이어진 구간 [(시작, 끝)] — 가까운 구간은 합친다."""
    idx = np.flatnonzero(mask_1d)
    if idx.size == 0:
        return []
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > min_gap:
            out.append((s, p))
            s = i
        p = i
    out.append((s, p))
    return out


class Reader:
    def __init__(self):
        self.cmd = tesseract_cmd()
        self.tessdata = tessdata_dir()
        self.tmp = Path(tempfile.mkdtemp())
        self.n = 0

    def ocr(self, img: Image.Image, psm: int = 6) -> str:
        self.n += 1
        p = self.tmp / f"c{self.n}.png"
        w, h = img.size
        canvas = Image.new("L", (w + 30, h + 30), 255)
        canvas.paste(img.convert("L"), (15, 15))
        canvas.save(p)
        args = [self.cmd, str(p), "-", "-l", "kor", "--psm", str(psm)]
        env = dict(os.environ)
        if self.tessdata:
            env["TESSDATA_PREFIX"] = self.tessdata
        r = subprocess.run(args, capture_output=True, env=env, timeout=60)
        return r.stdout.decode("utf-8", "replace").strip()


def page_cells(img: Image.Image):
    """쪽 그림 → [(띠 y0, y1, [칸 x0..x1 목록])] (가로줄 사이 띠마다 세로줄로 칸 나눔)"""
    a = np.asarray(img).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    dark = (r < 110) & (g < 110) & (b < 110)
    red = (r > 150) & (g < 110) & (b < 110)
    H, W = dark.shape
    hlines = [(s + e) // 2 for s, e in runs(dark.sum(axis=1) > W * 0.45)]
    bands = []
    for y0, y1 in zip(hlines, hlines[1:], strict=False):
        if y1 - y0 < 25:
            continue
        seg = dark[y0 + 3 : y1 - 2]
        vx = [(s + e) // 2 for s, e in runs(seg.mean(axis=0) > 0.9)]
        if len(vx) >= 2:
            bands.append((y0, y1, vx))
    return bands, dark, red


def read_cell(rd: Reader, img: Image.Image, dark, red, x0, y0, x1, y1) -> tuple[str, int]:
    m = 6
    x0, y0, x1, y1 = x0 + m, y0 + m, x1 - m, y1 - m
    if x1 - x0 < 10 or y1 - y0 < 10:
        return "", 0
    d, rr = dark[y0:y1, x0:x1], red[y0:y1, x0:x1]
    if d.sum() < 30:
        return "", 0
    crop = img.crop((x0, y0, x1, y1)).convert("RGB")
    struck = 0
    if rr.sum() > 200:  # 빨간 줄이 그어진 글줄은 통째로 지운다
        arr = np.asarray(crop).copy()
        ink = d | rr
        for s, e in runs(ink.any(axis=1), min_gap=4):
            width = max(1, ink[s : e + 1].any(axis=0).sum())
            if rr[s : e + 1].any(axis=0).sum() > width * 0.35:
                arr[max(0, s - 2) : e + 3] = 255
                struck += 1
        crop = Image.fromarray(arr)
    return rd.ocr(crop), struck


# 「갑」「을」 글자는 잘못 읽히기 쉬워(감·빨으) 괄호 안 설명으로 가린다
SECTION_KEYS = [
    ("을", re.compile(r"이\s*외")),
    ("갑", re.compile(r"소\s*유\s*권")),
    ("표제", re.compile(r"표\s*시|표\s*제\s*부")),
]


def ocr_rows(pdf: Path) -> tuple[list[dict], dict]:
    rd = Reader()
    rows: list[dict] = []
    section = None
    head = {"제목": None, "고유번호": None, "소재지": None}
    for pi, img in enumerate(render(pdf)):
        bands, dark, red = page_cells(img)
        if pi == 0 and bands:  # 첫 쪽 위쪽: 제목·고유번호·소재지
            top = rd.ocr(img.crop((0, 0, img.width, bands[0][0])), psm=6)
            head["제목"] = (re.search(r"등기사항\S*증명서\s*\(?[^)\n]*\)?", top) or [None])[0]
            if m := re.search(r"고유번호\s*([\d\-]{10,})", top):
                head["고유번호"] = m.group(1)
            if m := re.search(r"\[(?:집합건물|건물|토지)\]\s*(.+)", top):
                head["소재지"] = m.group(1).strip()
        for y0, y1, vx in bands:
            cells = list(zip(vx, vx[1:], strict=False))
            if len(cells) == 1:  # 한 칸짜리 띠 = 구 제목
                t = rd.ocr(img.crop((cells[0][0] + 4, y0 + 4, cells[0][1] - 4, y1 - 4)), psm=7)
                for name, pat in SECTION_KEYS:
                    if pat.search(t):
                        section = name
                        break
                continue
            if section not in ("갑", "을") or len(cells) != 5:
                continue
            texts, struck = [], 0
            for x0, x1 in cells:
                t, s = read_cell(rd, img, dark, red, x0, y0, x1, y1)
                texts.append(t)
                struck += s
            if re.sub(r"\s", "", texts[0]).startswith("순위") or "등기목적" in re.sub(
                r"\s", "", texts[1]
            ):
                continue  # 머리줄
            rank = re.sub(r"[^\d\-]", "", texts[0])
            row = {
                "구분": section,
                "순위번호": rank,
                "등기목적": texts[1],
                "접수": texts[2],
                "등기원인": texts[3],
                "권리자및기타": texts[4],
                "지운줄수": struck,
                "쪽": pi + 1,
            }
            if not rank and rows and rows[-1]["구분"] == section:  # 쪽이 바뀌며 이어진 줄
                for k in ("등기목적", "접수", "등기원인", "권리자및기타"):
                    rows[-1][k] = (rows[-1][k] + "\n" + row[k]).strip()
                rows[-1]["지운줄수"] += struck
                continue
            rows.append(row)
    head["인식횟수"] = rd.n
    return rows, head
