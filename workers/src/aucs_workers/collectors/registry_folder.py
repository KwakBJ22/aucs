"""등기부등본 받은 폴더(11/24 대표님 — 감정평가서처럼 폴더에 받아 두면 알아서 올라가게).

인터넷등기소에서 받은 등기부 PDF 를 D:\\Auction\\등기부등본(.env REGISTRY_INBOX) 에 두면 「관리자_요청」 작업(5분마다)이
등기부의 소재지로 우리 진행 물건을 찾아(지번 · 동 · 호가 같은 것 하나) 관리자가 올린 것처럼 넣습니다(손님 화면 「무엇을
떠안나」 등기부 칸 · 다른 회원에게도 공개, 포인트 없음 — 11/18). 넣은 것은 「넣음」, 못 넣은 것은 「못 넣음」 폴더로.
못 넣은 파일은 이름을 물건 번호(「2025타경57005-5.pdf」)로 바꿔 다시 두면 그 물건으로 넣습니다.
다운로드 폴더에 받은 등기부(글에 「등기사항」 · 갑구/을구, 그림 PDF 는 파일 이름에 「등기」)도 이 폴더로 옮깁니다 — 다른 PDF 는 안 건드림.
"""

import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from aucs_rules.address_match import _lot, compare

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

INBOX = r"D:\Auction\등기부등본"
DONE, MISS = "넣음", "못 넣음"
SEEN = Path(__file__).resolve().parents[4] / "logs" / "registry_downloads_seen.txt"
_ITEM = re.compile(r"(\d{4}타경\d+)(?:-(\d+))?")


def _text(raw: bytes) -> str:
    import io

    from pypdf import PdfReader

    try:
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages[:3])
    except Exception:  # noqa: BLE001
        return ""


def is_registry(name: str, text: str) -> bool:
    """등기부 PDF 인가(순수 함수): 글에 「등기사항」과 갑구/을구, 글 없는 그림 PDF 는 파일 이름에 「등기」."""
    if len(re.sub(r"\s", "", text)) > 100:
        return "등기사항" in text and bool(re.search(r"갑\s*구|을\s*구", text))
    return "등기" in name


def from_downloads(root: Path) -> int:
    dl = Path(os.getenv("REGISTRY_DOWNLOADS", "").strip() or os.getenv("APPRAISAL_DOWNLOADS", "").strip()
              or Path.home() / "Downloads")  # fmt: skip
    if not dl.is_dir():
        return 0
    now = time.time()
    seen = set(SEEN.read_text(encoding="utf-8").splitlines()) if SEEN.exists() else set()
    moved = 0
    for f in sorted(dl.iterdir()):
        if not (f.is_file() and f.suffix.lower() == ".pdf" and 15 < now - f.stat().st_mtime < 3 * 86400):
            continue
        key = f"{f.name}|{int(f.stat().st_mtime)}"
        if key in seen:
            continue
        seen.add(key)
        if is_registry(f.name, _text(f.read_bytes())):
            t = root / f.name
            if t.exists():
                t = root / f"{f.stem}-{int(now)}{f.suffix}"
            shutil.move(str(f), str(t))
            moved += 1
            print(f"   다운로드 → 등기부등본 폴더: {f.name}", flush=True)
    SEEN.parent.mkdir(exist_ok=True)
    SEEN.write_text("\n".join(sorted(seen)[-2000:]), encoding="utf-8")
    return moved


def find_item(conn, address: str | None, file_stem: str) -> tuple[str | None, str]:  # noqa: ANN001
    """(물건, 까닭). 파일 이름에 물건 번호가 있으면 그 사건 안에서, 없으면 지번이 같은 진행 물건 중 동 · 호까지 같은 하나."""
    m = _ITEM.search(file_stem.replace(" ", ""))
    if m:
        rows = conn.execute(
            "select i.item_id, i.address from core.items i where i.case_id like %s"
            + (" and i.item_no = %s" if m.group(2) else ""),
            (f"%-{m.group(1)}", int(m.group(2))) if m.group(2) else (f"%-{m.group(1)}",),
        ).fetchall()
        if len(rows) == 1:
            return rows[0][0], "파일 이름"
        rows = [r for r in rows if compare(address, r[1])["result"] == "same"]
        return (rows[0][0], "파일 이름 + 주소") if len(rows) == 1 else (None, f"사건 안 물건 {len(rows)}개")
    lot = _lot(address or "")
    if not lot:
        return None, "등기부에서 소재지 · 지번을 못 읽음"
    rows = conn.execute(
        """select i.item_id, i.address from core.items i
           where i.address like %s and i.sale_date >= current_date - 7 and i.status_code is distinct from 'gone'""",
        (f"%{lot}%",),
    ).fetchall()
    same = [r[0] for r in rows if compare(address, r[1])["result"] == "same"]
    if len(same) == 1:
        return same[0], "주소"
    return None, "주소 맞는 진행 물건 없음" if not same else f"주소 맞는 물건 {len(same)}개 — 파일 이름을 물건 번호로"


def inbox(folder: str | None = None) -> str | None:
    """등기부등본 받은 폴더(5분마다). 한 줄 결과, 할 일이 없으면 None."""
    root = Path(folder or os.getenv("REGISTRY_INBOX", "").strip() or INBOX)
    root.mkdir(parents=True, exist_ok=True)  # 처음이면 폴더를 만들어 둠
    try:
        from_downloads(root)
    except Exception as e:  # noqa: BLE001
        print(f"   다운로드 폴더 보기(등기부) 실패: {e}", flush=True)
    now = time.time()
    files = [f for f in sorted(root.iterdir())
             if f.is_file() and f.suffix.lower() == ".pdf" and now - f.stat().st_mtime > 15]  # fmt: skip
    if not files:
        return None
    # PC 는 한 저장소라 API 코드를 그대로 씀(registry_ocr 와 같게)
    from aucs_api.services import registry

    from aucs_workers.extract.registry import read_pdf

    miss: list[str] = []
    with connect() as conn, run(conn, "registry_inbox", "등기부등본 받은 폴더") as job:
        owner = conn.execute(
            "select user_id from app.admins where role = 'owner' limit 1"
        ).fetchone()
        for f in files:
            item, why = None, "관리자(대표) 계정 없음"
            try:
                if owner:
                    raw = f.read_bytes()
                    with tempfile.TemporaryDirectory() as d:
                        p = Path(d) / "r.pdf"
                        p.write_bytes(raw)
                        _, meta = read_pdf(p)
                    item, why = find_item(conn, meta.get("소재지"), f.stem)
                    if item:
                        uid = registry.save_upload(str(owner[0]), item, f.name, raw)
                        registry.parse_upload(uid, ocr=True)
            except Exception as e:  # noqa: BLE001 — 한 파일 탈이 나머지를 막지 않게
                conn.rollback()
                item, why = None, f"오류 {type(e).__name__}"
            to = root / (DONE if item else MISS)
            to.mkdir(exist_ok=True)
            t = to / f.name
            if t.exists():
                t = to / f"{f.stem}-{int(now)}{f.suffix}"
            f.rename(t)
            if item:
                job.count += 1
            else:
                miss.append(f"{f.name}({why})")
            print(f"   {f.name} → {item or '못 넣음'} · {why}", flush=True)
        msg = f"{root} · 넣음 {job.count}" + (f" · 못 넣음 {len(miss)}: {', '.join(miss)}" if miss else "")
        conn.execute("update ops.job_runs set message = %s where run_id = %s", (msg[:500], job.run_id))
        conn.commit()
    return msg


if __name__ == "__main__":
    print(inbox())
