"""정비사업 대표지번 → 좌표(브이월드 주소 좌표 검색) → ref.place_points (11/13 「입지 — 가까운 정비사업」).

    uv run python -m aucs_workers.collectors.redev_geo            # 아직 좌표 없는 곳만(처음 약 1,100곳 · 4분쯤)
    uv run python -m aucs_workers.collectors.redev_geo --probe    # 한 곳만 받아 응답을 보여 줌

- 정비사업 목록을 새로 받으면(redev) 끝에 이것을 이어 돌림. 한 번 받은 주소는 다시 묻지 않음(못 찾은 곳 포함).
- 키: .env 의 VWORLD_API_KEY(공시가격과 같은 키). 인증 · 한도 오류면 받은 데까지 두고 멈춤.
"""

import argparse
import os
import time

import httpx
from aucs_rules.location import ZONE_ADDRESS_SQL

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

URL = "https://api.vworld.kr/req/address"
GAP = 0.2
TARGETS_SQL = f"""
select distinct {ZONE_ADDRESS_SQL} as address
from ref.redev_zones z
where z.dong_name is not null and z.main_no is not null
  and not exists (select 1 from ref.place_points p where p.address = {ZONE_ADDRESS_SQL})
order by 1
"""


class ApiError(Exception):
    pass


def geocode(client: httpx.Client, key: str, domain: str, address: str) -> tuple[float, float] | None:
    """지번 주소 → (경도, 위도). 못 찾으면 None, 인증 · 한도 등 오류면 ApiError."""
    r = client.get(URL, params={"service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326",
                                "type": "parcel", "refine": "true", "simple": "false", "format": "json",
                                "address": address, "key": key, "domain": domain})  # fmt: skip
    try:
        res = r.json()["response"]
    except (ValueError, KeyError) as e:
        raise ApiError(f"HTTP {r.status_code} · {r.text[:200]}") from e
    if res.get("status") == "OK":
        p = res["result"]["point"]
        return float(p["x"]), float(p["y"])
    if res.get("status") == "NOT_FOUND":
        return None
    raise ApiError(str(res.get("error") or res)[:300])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="한 곳만 받아 응답을 보여 줌(저장도 함)")
    a = ap.parse_args()
    key = os.getenv("VWORLD_API_KEY", "").strip().strip("\"'")
    domain = os.getenv("VWORLD_DOMAIN", "https://aucs.co.kr").strip()
    if not key:
        raise SystemExit("VWORLD_API_KEY 가 비어 있습니다 (.env)")
    with connect() as conn, run(conn, "redev_geo", "정비사업 좌표") as job:
        rows = [r[0] for r in conn.execute(TARGETS_SQL).fetchall()]
        if a.probe:
            rows = rows[:1]
        print(f"[시작] 주소 {len(rows):,}곳")
        ok = 0
        with httpx.Client(timeout=30) as client:
            for i, address in enumerate(rows, 1):
                time.sleep(GAP)
                try:
                    pt = geocode(client, key, domain, address)
                except (ApiError, httpx.HTTPError) as e:
                    conn.commit()
                    print(f"\n[멈춤] {address}: {e}\n  키 · 하루 한도를 확인하세요. 받은 데까지 저장했어요.")
                    raise SystemExit(1) from e
                if a.probe:
                    print(f"--- {address} → {pt}")
                conn.execute(
                    """insert into ref.place_points (address, geom, result)
                       values (%s, case when %s::float8 is null then null
                                        else st_setsrid(st_makepoint(%s::float8, %s::float8), 4326)::geography end, %s)
                       on conflict (address) do nothing""",
                    (address, pt[0] if pt else None, pt[0] if pt else None, pt[1] if pt else None,
                     "ok" if pt else "none"),
                )  # fmt: skip
                ok += bool(pt)
                if i % 100 == 0:
                    conn.commit()
                    print(f"  {i:,}/{len(rows):,} · 찾음 {ok:,}")
        job.count = ok
    print(f"끝: 주소 {len(rows):,}곳 · 좌표 찾음 {ok:,}곳")


if __name__ == "__main__":
    main()
