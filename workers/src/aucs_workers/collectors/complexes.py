"""공동주택 단지 식별정보(한국부동산원) → ref.complexes (분기 갱신, 11/16).

    uv run python -m aucs_workers.collectors.complexes

- 공공데이터포털 15106817 「공동주택 단지 식별정보」 — api.odcloud.kr AptIdInfoSvc/v1 의 getAptInfo(단지) ·
  getDongInfo(동). 전국 약 30만 단지 · 47만 동을 받아 수도권(필지번호 앞 11 · 41 · 28)만 남김.
- 필지번호(PNU)로 물건에 이음 — 세대수 · 동수 · 사용승인일 · 동마다 지상 층수. 7세대 빌라까지 있음.
- 표를 통째로 갈아 끼움(받다 끊기면 그대로 둠). 키: .env 의 DATA_GO_KR_SERVICE_KEY(Encoding 꼴 → 풀어 씀).
- 이주 0062 가 적용돼 있어야 함. 정비사업 목록(redev)을 받을 때 같이 돎.
"""

import os
import re
import time
from datetime import date
from typing import Any
from urllib.parse import unquote

import httpx
from psycopg.types.json import Jsonb

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

BASE = "https://api.odcloud.kr/api/AptIdInfoSvc/v1"
PER = 1000
CAPITAL = ("11", "41", "28")  # 서울 · 경기 · 인천


def pages(client: httpx.Client, key: str, op: str) -> list[dict[str, Any]]:
    """한 가지(단지 · 동)를 끝까지. 한 쪽이 세 번 실패하면 멈춤(표를 반쯤 갈지 않게)."""
    out: list[dict[str, Any]] = []
    page, total = 1, None
    while total is None or (page - 1) * PER < total:
        for attempt in range(3):
            time.sleep(0.2)
            try:
                r = client.get(
                    f"{BASE}/{op}", params={"serviceKey": key, "page": page, "perPage": PER}
                )
                d = r.json()
                break
            except (httpx.HTTPError, ValueError):
                time.sleep(3 * (attempt + 1))
        else:
            raise SystemExit(f"{op} {page}쪽을 못 받음 — 표는 그대로 둠")
        if "data" not in d:
            raise SystemExit(f"{op} 응답 이상: {str(d)[:160]}")
        total = int(d.get("totalCount") or 0)
        out += d["data"] or []
        if not d["data"]:
            break
        page += 1
        if page % 50 == 0:
            print(f"  {op} {len(out):,}/{total:,}")
    return out


def _day(v: Any) -> str | None:
    s = re.sub(r"\D", "", str(v or ""))
    if len(s) != 8:
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()
    except ValueError:
        return None


def _int(v: Any) -> int | None:
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def to_rows(apts: list[dict[str, Any]], dongs: list[dict[str, Any]]) -> list[tuple]:
    """API 줄 → ref.complexes 줄 (순수 함수). 수도권 필지번호만."""
    by: dict[str, list[dict[str, Any]]] = {}
    for d in dongs:
        name = next((d.get(k) for k in ("DONG_NM1", "DONG_NM2", "DONG_NM3") if d.get(k)), None)
        by.setdefault(str(d.get("COMPLEX_PK")), []).append(
            {"name": name, "floors": _int(d.get("GRND_FLR_CNT"))}
        )
    rows = []
    for a in apts:
        pnu, pk = str(a.get("PNU") or ""), str(a.get("COMPLEX_PK") or "")
        if not pk or not pnu.startswith(CAPITAL):
            continue
        names = [
            str(a[k]).strip() for k in ("COMPLEX_NM1", "COMPLEX_NM2", "COMPLEX_NM3") if a.get(k)
        ]
        ds = by.get(pk, [])
        floors = [x["floors"] for x in ds if x["floors"]]
        rows.append(
            (pk, pnu, a.get("ADRES"), a.get("ROAD_ADRES"), names, str(a.get("COMPLEX_GB_CD") or ""),
             _int(a.get("DONG_CNT")), _int(a.get("UNIT_CNT")), _day(a.get("USEAPR_DT")),
             Jsonb(ds), max(floors) if floors else None)
        )  # fmt: skip
    return rows


def main() -> None:
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 가 비어 있습니다 (.env)")
    with connect() as conn:
        if not conn.execute("select to_regclass('ref.complexes')").fetchone()[0]:
            raise SystemExit("ref.complexes 가 아직 없음(이주 0062 적용 전)")
        with run(conn, "complexes", "공동주택 단지 식별정보") as job:
            with httpx.Client(timeout=60, headers={"Accept": "application/json"}) as c:
                apts = pages(c, key, "getAptInfo")
                dongs = pages(c, key, "getDongInfo")
            rows = to_rows(apts, dongs)
            print(f"[받음] 전국 단지 {len(apts):,} · 동 {len(dongs):,} → 수도권 단지 {len(rows):,}")
            if len(rows) < 10_000:
                raise SystemExit(f"수도권 단지가 {len(rows):,}곳뿐 — 이상해서 표를 그대로 둠")
            conn.execute("delete from ref.complexes")
            with (
                conn.cursor() as cur,
                cur.copy(
                    "copy ref.complexes (complex_pk, pnu, address, road_address, names, gb_cd, dong_cnt,"
                    " unit_cnt, use_approved, dongs, max_floors) from stdin"
                ) as cp,
            ):
                for r in rows:
                    cp.write_row(r)
            conn.commit()
            job.count = len(rows)
    print(f"끝: 수도권 단지 {len(rows):,}곳")


if __name__ == "__main__":
    main()
