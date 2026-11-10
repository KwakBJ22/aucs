"""대표님이 받아 둔 감정평가서 원본(PDF) 폴더 → raw 'appraisal_pdf' (11/11 대표님 — 원본은 따로 받기로).

폴더의 PDF 를 읽어 회사 이름 · 쪽수 · 앞부분 글 · 요항표를 남깁니다(kapa_pdf 와 같은 꼴, PDF 자체는 저장하지 않음).
어느 사건인지는 ① 글 속 사건번호(「2025타경56683」) ② 파일 이름 = 감정서 번호(법원 감정평가서 정보) 순으로 찾습니다.
법원 · KAPA 에 접속하지 않습니다. 같은 파일(이름만 다른 복사본)은 한 번만.

    cd D:\\Auction\\auction-platform\\workers
    uv run python -m aucs_workers.collectors.appraisal_folder D:\\Auction\\감정평가서
    uv run python -m aucs_workers.collectors.appraisal_folder D:\\Auction\\감정평가서 --court B000250   # 법원을 못 박을 때
"""

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from aucs_workers.collectors.parse import checksum
from aucs_workers.db import connect
from aucs_workers.extract.appraisal_pdf import case_numbers, read_pdf
from aucs_workers.jobs.runlog import run


def appraisal_no(path: Path) -> str:
    """파일 이름 → 감정서 번호(「2025-1-049 (2).pdf」의 복사 꼬리는 뗌)."""
    return re.sub(r"\s*\(\d+\)$", "", path.stem).strip()


def find_case(conn: psycopg.Connection, data: dict[str, Any], no: str, court: str | None) -> list[str]:
    """이 PDF 의 사건 — 글 속 사건번호로, 없으면 감정서 번호로. 여러 법원에 같은 번호가 있으면 모두 돌려줌(그때는 넣지 않음)."""
    for cs in case_numbers(str(data.get("head") or "")):
        rows = conn.execute(
            "select distinct case_id from core.items where case_id like %s and (%s::text is null or case_id like %s)",
            (f"%-{cs}", court, f"{court}-%"),
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
    rows = conn.execute(
        """select distinct case_id from raw.court_doc_raw
           where doc_kind = 'appraisal' and payload -> 'info' ->> 'aeeWevlNo' = %s""",
        (no,),
    ).fetchall()
    return [r[0] for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--court", help="법원 코드(같은 사건번호가 여러 법원에 있을 때)")
    a = ap.parse_args()
    seen: set[str] = set()
    miss: list[str] = []
    with connect() as conn, run(conn, "appraisal_folder", "감정평가서 폴더") as job:
        for f in sorted(Path(a.folder).glob("*.pdf")):
            raw = f.read_bytes()
            h = hashlib.md5(raw).hexdigest()  # noqa: S324 — 같은 파일 가리기용
            if h in seen:
                continue
            seen.add(h)
            no = appraisal_no(f)
            try:
                data = {"no": no, "from": "folder", **read_pdf(raw)}
            except Exception as e:  # noqa: BLE001 — 깨진 PDF 는 건너뜀
                miss.append(f"{f.name} (못 읽음 {type(e).__name__})")
                continue
            cases = find_case(conn, data, no, a.court)
            if len(cases) != 1:
                miss.append(f"{f.name} ({'사건 못 찾음' if not cases else '법원 여럿 ' + ', '.join(cases)})")
                continue
            conn.execute(
                "insert into raw.court_doc_raw (case_id, doc_kind, payload, checksum) values (%s,'appraisal_pdf',%s,%s) on conflict do nothing",
                (cases[0], Jsonb(data), checksum(data)),
            )
            conn.commit()
            job.count += 1
            print(f"   {cases[0]} {data['firm'] or '회사 이름 못 찾음'} · {data['pages']}쪽 · 요항 {len(data['points'])}칸"
                  + (" · 그림 PDF(글 없음)" if data["scanned"] else ""))  # fmt: skip
    print(f"끝: {job.count}건" + (f" · 못 넣은 것 {len(miss)}건" if miss else ""))
    for m in miss:
        print(f"   - {m}")


if __name__ == "__main__":
    main()
