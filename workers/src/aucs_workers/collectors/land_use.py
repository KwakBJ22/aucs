"""토지이용계획(브이월드 getLandUseAttr) — 필지에 걸린 지역 · 지구(정비구역 등). 11/14: 받아지는지 보는 시험만.

    uv run python -m aucs_workers.collectors.land_use --probe B000212-2026타경3952-1

감정평가서가 아직 없는 물건의 「정비구역 안」을 가리려는 것. 응답 꼴을 본 뒤 수집 · 저장을 붙임(지금은 저장 안 함).
키: .env 의 VWORLD_API_KEY(공시가격과 같은 키 — 서비스에 국가중점데이터 포함).
"""

import argparse
import os

import httpx

from aucs_workers.collectors.official_prices import pnu_of
from aucs_workers.db import connect

URL = "https://api.vworld.kr/ned/data/getLandUseAttr"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True, help="물건 번호 — 그 필지 한 곳만 받아 응답을 보여 줌")
    a = ap.parse_args()
    key = os.getenv("VWORLD_API_KEY", "").strip().strip("\"'")
    domain = os.getenv("VWORLD_DOMAIN", "https://aucs.co.kr").strip()
    if not key:
        raise SystemExit("VWORLD_API_KEY 가 비어 있습니다 (.env)")
    with connect() as conn:
        row = conn.execute(
            "select region_code, lot_no, address from core.items where item_id = %s", (a.probe,)
        ).fetchone()
    if not row or not (pnu := pnu_of(row[0], row[1])):
        raise SystemExit(f"{a.probe}: 물건이 없거나 지번을 못 읽음")
    r = httpx.get(URL, params={"key": key, "domain": domain, "pnu": pnu, "format": "json",
                               "numOfRows": 100, "pageNo": 1}, timeout=30)  # fmt: skip
    print(f"--- {row[2]} · pnu {pnu} · HTTP {r.status_code}")
    print((r.text or "")[:3000].replace(key, "***"))


if __name__ == "__main__":
    main()
