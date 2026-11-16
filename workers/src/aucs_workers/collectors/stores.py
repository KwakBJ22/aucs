"""상가 물건 주변 가게 — 소상공인시장진흥공단 상가(상권)정보 → core.item_stores (11/16).

    uv run python -m aucs_workers.collectors.stores            # 아침 묶음: 하루 500건
    uv run python -m aucs_workers.collectors.stores --cap 20

- 공공데이터포털 15012005 「상가(상권)정보」 storeListInRadius(반경 300m). 가게 줄은 두지 않고 업종별 수만.
- 같은 필지(가게의 lnoCd = 물건의 필지번호)에 든 가게는 층 · 호 · 업종만 따로 — 「이 건물에 든 가게」.
- 대상: 진행 중인 상가 · 근린시설 물건(좌표 있는 것). 관심 물건 → 매각기일 가까운 순. 받은 물건은 90일 안에 다시 안 받음.
- 하루 한도 · 인증 오류면 받은 데까지 저장하고 멈춤. 이주 0063 이 없으면 건너뜀.
"""

import argparse
import os
import time
from collections import Counter
from typing import Any
from urllib.parse import unquote

import httpx
from aucs_rules.building import parse_jibun
from psycopg.types.json import Jsonb

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

URL = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius"
RADIUS = 300
ROWS = 1000

TARGETS_SQL = """
select i.item_id, i.region_code, i.lot_no, st_x(i.geom::geometry), st_y(i.geom::geometry)
from core.items i
left join core.item_stores s on s.item_id = i.item_id
where i.sale_date >= current_date and i.status_code is distinct from 'gone' and i.geom is not null
  and i.usage_name ~ '(상가|근린)'
  and (s.item_id is null or s.fetched_at < now() - interval '90 days')
order by not exists (select 1 from app.watch_items w where w.item_id = i.item_id), i.sale_date, i.item_id
limit %(cap)s
"""


class ApiError(Exception):
    pass


def pnu(code10: str, lot: str | None) -> str | None:
    """물건 법정동코드 + 지번 → 필지번호 19자리(일반 1 · 산 2)."""
    p = parse_jibun(lot)
    if not p or len(code10 or "") != 10:
        return None
    return f"{code10}{int(p[0]) + 1}{p[1]}{p[2]}"


def _items(d: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    body = d.get("body") or (d.get("response") or {}).get("body") or {}
    header = d.get("header") or (d.get("response") or {}).get("header") or {}
    code = str(header.get("resultCode") or "00")
    if code == "03":  # 자료 없음
        return [], 0
    if code not in ("00", "0"):
        raise ApiError(f"{code} {header.get('resultMsg')}")
    its = body.get("items") or []
    if isinstance(its, dict):
        its = its.get("item") or []
    return ([its] if isinstance(its, dict) else its), int(body.get("totalCount") or 0)


def fetch(client: httpx.Client, key: str, lon: float, lat: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        body = ""
        for attempt in range(4):
            time.sleep(0.3)
            try:
                r = client.get(URL, params={"serviceKey": key, "radius": RADIUS, "cx": lon, "cy": lat,
                                            "numOfRows": ROWS, "pageNo": page, "type": "json"})  # fmt: skip
                body = (r.text or "").strip()
            except httpx.HTTPError:
                body = ""
            if body:
                break
            time.sleep(2 * (attempt + 1))
        if not body.startswith("{"):
            raise ApiError(body[:160] or "빈 응답")
        part, total = _items(r.json())
        out += part
        if not part or page * ROWS >= total:
            return out
        page += 1


def summarize(stores: list[dict[str, Any]], parcel: str | None) -> dict[str, Any]:
    """가게 줄 → 업종별 수 · 같은 필지 가게 (순수 함수)."""
    large = Counter(str(s.get("indsLclsNm") or "").strip() or "기타" for s in stores)
    mid = Counter(str(s.get("indsMclsNm") or "").strip() or "기타" for s in stores)
    same = [s for s in stores if parcel and str(s.get("lnoCd") or "") == parcel]
    return {
        "total": len(stores),
        "by_large": dict(large.most_common()),
        "by_mid": dict(mid.most_common(15)),
        "same_parcel": len(same),
        "same_list": [
            {
                "floor": s.get("flrNo") or None,
                "ho": s.get("hoNo") or None,
                "large": s.get("indsLclsNm"),
                "small": s.get("indsSclsNm"),
            }
            for s in same[:60]
        ],  # fmt: skip
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=500)
    a = ap.parse_args()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 가 비어 있습니다 (.env)")
    with connect() as conn:
        if not conn.execute("select to_regclass('core.item_stores')").fetchone()[0]:
            print("core.item_stores 가 아직 없음(이주 0063 적용 전) — 건너뜀")
            return
        with run(conn, "stores", "상가 주변 가게") as job:
            todo = conn.execute(TARGETS_SQL, {"cap": a.cap}).fetchall()
            print(f"[시작] 물건 {len(todo):,}건")
            with httpx.Client(timeout=40, headers={"Accept": "application/json"}) as client:
                for i, (item_id, code, lot, lon, lat) in enumerate(todo, 1):
                    try:
                        stores = fetch(client, key, lon, lat)
                    except ApiError as e:
                        print(f"\n[멈춤] {e} — 하루 한도 · 활용신청을 확인하세요. 받은 데까지 저장했어요.")  # fmt: skip
                        conn.commit()
                        raise
                    s = summarize(stores, pnu(code, lot))
                    conn.execute(
                        """insert into core.item_stores (item_id, radius_m, total, by_large, by_mid,
                             same_parcel, same_list, fetched_at)
                           values (%s, %s, %s, %s, %s, %s, %s, now())
                           on conflict (item_id) do update set radius_m = excluded.radius_m,
                             total = excluded.total, by_large = excluded.by_large,
                             by_mid = excluded.by_mid, same_parcel = excluded.same_parcel,
                             same_list = excluded.same_list, fetched_at = now()""",
                        (item_id, RADIUS, s["total"], Jsonb(s["by_large"]), Jsonb(s["by_mid"]),
                         s["same_parcel"], Jsonb(s["same_list"])),
                    )  # fmt: skip
                    job.count += 1
                    if i % 50 == 0:
                        conn.commit()
                        print(f"  {i:,}/{len(todo):,}")
            conn.commit()
    print(f"끝: 물건 {job.count:,}건")


if __name__ == "__main__":
    main()
