"""토지이용계획(브이월드 getLandUseAttr) — 필지에 걸린 지역 · 지구(정비구역 등) → core.parcel_land_use (11/14).

    uv run python -m aucs_workers.collectors.land_use                 # 아침 묶음: 아직 안 받은 필지(기본 3,000곳)
    uv run python -m aucs_workers.collectors.land_use --cap 20000     # 처음 한 번 따라잡기
    uv run python -m aucs_workers.collectors.land_use --probe B000212-2026타경3952-1   # 한 곳만 받아 응답 보기

- 감정평가서가 아직 없는 물건도 「정비구역 안」을 가리려는 것(분석이 감정평가 요항 글 다음으로 읽음).
- 진행 중인 물건의 필지만, 매각기일 가까운 순. 같은 필지는 180일 안에 다시 받지 않음(지정은 자주 안 바뀜).
- 키: .env 의 VWORLD_API_KEY(공시가격과 같은 키). 인증 · 한도 오류면 받은 데까지 두고 멈춤.
"""

import argparse
import json
import os
import time
from typing import Any

import httpx
from psycopg.types.json import Jsonb

from aucs_workers.collectors.official_prices import pnu_of
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

URL = "https://api.vworld.kr/ned/data/getLandUseAttr"
GAP = 0.2
ROWS = 100
TARGETS_SQL = """
select i.region_code, i.lot_no, min(i.sale_date) as d
from core.items i
where i.sale_date >= current_date and i.status_code is distinct from 'gone'
  and i.region_code is not null and i.lot_no is not null
group by 1, 2 order by d
"""


class ApiError(Exception):
    pass


def fetch(client: httpx.Client, key: str, domain: str, pnu: str) -> tuple[list[dict[str, Any]], str]:
    """한 필지의 지역 · 지구 목록(줄인 꼴)과 응답 원문 앞부분."""
    out: list[dict[str, Any]] = []
    page, text = 1, ""
    while True:
        time.sleep(GAP)
        r = client.get(URL, params={"key": key, "domain": domain, "pnu": pnu, "format": "json",
                                    "numOfRows": ROWS, "pageNo": page})  # fmt: skip
        text = (r.text or "").strip()
        if r.status_code != 200 or not text.startswith("{"):
            raise ApiError(f"HTTP {r.status_code} {text[:160]}")
        last = json.loads(text)
        body = next((v for v in last.values() if isinstance(v, dict)), {})
        err = body.get("error") or last.get("error")
        if err:
            raise ApiError(str(err)[:160])
        part = body.get("field") or []
        part = [part] if isinstance(part, dict) else part
        out += [{"name": x.get("prposAreaDstrcCodeNm"), "code": x.get("prposAreaDstrcCode"),
                 "incl": x.get("cnflcAtNm"), "since": x.get("registDt")} for x in part]  # fmt: skip
        total = int(body.get("totalCount") or len(out))
        if not part or len(out) >= total:
            return out, text
        page += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=3000)
    ap.add_argument("--probe", help="물건 번호 — 그 필지 한 곳만 받아 응답을 보여 줌(저장도 함)")
    a = ap.parse_args()
    key = os.getenv("VWORLD_API_KEY", "").strip().strip("\"'")
    domain = os.getenv("VWORLD_DOMAIN", "https://aucs.co.kr").strip()
    if not key:
        raise SystemExit("VWORLD_API_KEY 가 비어 있습니다 (.env)")
    with connect() as conn, run(conn, "land_use", "토지이용계획") as job:
        if a.probe:
            row = conn.execute(
                "select region_code, lot_no from core.items where item_id = %s", (a.probe,)
            ).fetchone()
            pnus = [p] if row and (p := pnu_of(row[0], row[1])) else []
        else:
            have = {r[0] for r in conn.execute(
                "select pnu from core.parcel_land_use where fetched_at > now() - interval '180 days'"
            ).fetchall()}  # fmt: skip
            pnus = list(dict.fromkeys(
                p for code, lot, _ in conn.execute(TARGETS_SQL).fetchall()
                if (p := pnu_of(code, lot)) and p not in have
            ))[: a.cap]  # fmt: skip
        print(f"[시작] 필지 {len(pnus):,}곳")
        n = 0
        with httpx.Client(timeout=30, headers={"Accept": "application/json"}) as client:
            for i, pnu in enumerate(pnus, 1):
                try:
                    uses, text = fetch(client, key, domain, pnu)
                except (ApiError, httpx.HTTPError) as e:
                    conn.commit()
                    print(f"\n[멈춤] {pnu}: {e}\n  키 · 하루 한도를 확인하세요. 받은 데까지 저장했어요.")
                    raise SystemExit(1) from e
                if a.probe:
                    print(f"--- pnu {pnu}\n" + text[:1500].replace(key, "***"))
                    print("줄인 꼴:", [f"{u['name']}({u['incl']})" for u in uses])
                conn.execute(
                    """insert into core.parcel_land_use (pnu, uses) values (%s, %s)
                       on conflict (pnu) do update set uses = excluded.uses, fetched_at = now()""",
                    (pnu, Jsonb(uses)),
                )
                n += 1
                if i % 200 == 0:
                    conn.commit()
                    print(f"  {i:,}/{len(pnus):,}")
        job.count = n
    print(f"끝: 필지 {n:,}곳")


if __name__ == "__main__":
    main()
