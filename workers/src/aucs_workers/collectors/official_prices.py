"""공시가격(브이월드 국가중점데이터) — 진행 중인 경매 물건만 받아 raw.official_price_raw 에 (11/11 대표님).

재산세·종부세 셈의 바탕(공시가격 × 공정시장가액비율). 법원과 다른 곳이라 법원 하루 한도와 상관없음.

    uv run python -m aucs_workers.collectors.official_prices --probe   # 한 건만 — 응답을 화면에 보여 줌(처음 한 번)
    uv run python -m aucs_workers.collectors.official_prices           # 아침 묶음: 기본 800건

- 아파트·연립·다세대 → 공동주택가격(apt) · 단독·다가구·근린주택 → 개별주택가격(house) · 모든 물건 → 개별공시지가(land, ㎡당).
- 같은 물건은 180일 안에 다시 받지 않음(공시는 한 해 한 번). 올해 것이 없으면 지난해 것.
- 키: .env 의 VWORLD_API_KEY (브이월드 「인증키 발급」 · 서비스에 국가중점데이터 포함). 하루 한도·인증 오류면 받은 데까지 두고 멈춤.
"""

import argparse
import json
import os
import re
import time
from datetime import date
from typing import Any

import httpx
from aucs_rules.building import dong_key, ho_from_address, parse_jibun, unit_from_address
from aucs_rules.holding_tax import dong_matches
from psycopg.types.json import Jsonb

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

BASE = "https://api.vworld.kr/ned/data"
OPS = {"apt": "getApartHousingPriceAttr", "house": "getIndvdHousingPriceAttr", "land": "getIndvdLandPriceAttr"}
GAP = 0.1
ROWS = 1000
APT = re.compile(r"(아파트|연립|다세대|빌라|공동주택)")
HOUSE = re.compile(r"(단독|다가구|근린주택|주택)")

TARGETS_SQL = """
select i.item_id, i.region_code, i.lot_no, coalesce(i.usage_name, '') || ' ' || coalesce(i.building_desc, '') as usage,
       i.address
from core.items i
where i.sale_date >= current_date and i.status_code is distinct from 'gone'
  and length(i.region_code) = 10 and coalesce(i.lot_no, '') <> ''
  and not exists (select 1 from raw.official_price_raw r where r.item_id = i.item_id and r.kind = 'land'
                  and r.fetched_at > now() - interval '180 days')
order by exists (select 1 from app.watch_items w where w.item_id = i.item_id) desc, i.sale_date
limit %s
"""


RECHECK_SQL = """
select i.item_id, i.region_code, i.lot_no, coalesce(i.usage_name, '') || ' ' || coalesce(i.building_desc, '') as usage,
       i.address, r.payload -> 'items' -> 0 ->> 'dongNm'
from core.items i join raw.official_price_raw r on r.item_id = i.item_id and r.kind = 'apt'
where i.sale_date >= current_date and length(i.region_code) = 10 and coalesce(i.lot_no, '') <> ''
"""


class ApiError(Exception):
    pass


def pnu_of(region_code: str, lot_no: str) -> str | None:
    """법정동 10자리 + 지번 → 필지 번호 19자리(산이면 2, 아니면 1)."""
    p = parse_jibun(lot_no)
    if not p:
        return None
    plat, bun, ji = p
    return f"{region_code}{'2' if plat == '1' else '1'}{bun}{ji}"


def kinds_for(usage: str) -> list[str]:
    """물건 쓰임새 → 받을 공시가격 종류(땅값은 늘)."""
    if APT.search(usage):
        return ["apt", "land"]
    if HOUSE.search(usage) and "오피스텔" not in usage:
        return ["house", "land"]
    return ["land"]


def fetch(client: httpx.Client, key: str, domain: str, kind: str, pnu: str, year: int) -> dict[str, Any]:
    """한 종류 · 한 해. 응답을 그대로 돌려줌(쪽이 여럿이면 합침)."""
    items: list[Any] = []
    page, total, last = 1, 0, {}
    while True:
        time.sleep(GAP)
        r = client.get(f"{BASE}/{OPS[kind]}", params={
            "key": key, "domain": domain, "pnu": pnu, "stdrYear": year, "format": "json",
            "numOfRows": ROWS, "pageNo": page})  # fmt: skip
        text = (r.text or "").strip()
        if r.status_code != 200 or not text.startswith("{"):
            raise ApiError(f"HTTP {r.status_code} {text[:160]}")
        last = json.loads(text)
        body = next((v for v in last.values() if isinstance(v, dict)), {})  # 응답 이름이 API 마다 다름
        err = body.get("error") or last.get("error")
        if err:
            raise ApiError(str(err)[:160])
        part = body.get("field") or []
        part = [part] if isinstance(part, dict) else part
        items += part
        total = int(body.get("totalCount") or len(items))
        if not part or len(items) >= total:
            break
        page += 1
    return {"year": year, "total": total, "items": items}


def _digits(v: Any) -> str:
    return re.sub(r"\D", "", str(v or "")).lstrip("0")


def pick_unit(items: list[dict[str, Any]], address: str | None) -> list[dict[str, Any]]:
    """공동주택은 단지 전체가 옴 → 이 물건의 동·호(dongNm·hoNm) 한 줄만 남김. 같은 집이 여러 줄이면 최근 고친 것.
    못 고르면 빈 목록(DB 를 아끼려고 단지 전체는 두지 않음)."""
    ho = _digits(ho_from_address(address))
    dong = dong_key(unit_from_address(address)["dong"])
    if not ho:
        return []
    hits = [x for x in items
            if _digits(x.get("hoNm")) == ho
            and (not dong or not dong_key(x.get("dongNm")) or dong_key(x.get("dongNm")) == dong)]  # fmt: skip
    if not dong and len({dong_key(x.get("dongNm")) for x in hits}) > 1:
        return []  # 주소에 동이 없는데 같은 호수가 여러 동에 있음 → 어느 집인지 모름(11/11 — 다른 동 값이 붙던 것)
    if not hits:
        return []
    return [max(hits, key=lambda x: (str(x.get("stdrYear")), str(x.get("stdrMt")), str(x.get("lastUpdtDt"))))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=800)
    ap.add_argument("--probe", action="store_true", help="한 건만 받아 응답을 보여 줌(저장도 함)")
    ap.add_argument("--recheck", action="store_true", help="이미 받은 아파트·빌라 중 동이 안 맞는 것만 다시 받음(11/11)")
    a = ap.parse_args()
    key = os.getenv("VWORLD_API_KEY", "").strip().strip("\"'")
    domain = os.getenv("VWORLD_DOMAIN", "https://aucs.co.kr").strip()
    if not key:
        raise SystemExit("VWORLD_API_KEY 가 비어 있습니다 (.env)")
    this_year = date.today().year
    with connect() as conn, run(conn, "official_prices", "공시가격") as job:
        if a.recheck:
            rows = [
                (x[0], x[1], x[2], x[3], x[4])
                for x in conn.execute(RECHECK_SQL).fetchall()
                if not dong_matches(x[4], x[5])
            ][: a.cap]
        else:
            rows = conn.execute(TARGETS_SQL, (1 if a.probe else a.cap,)).fetchall()
        rows.sort(key=lambda r: (r[1], r[2]))  # 같은 필지끼리 붙여 한 번 받은 것을 바로 다시 씀(관심·날짜 순은 cap 안에서만)
        print(f"[시작] 물건 {len(rows):,}건")
        cache: dict[tuple[str, str], dict[str, Any]] = {}  # 같은 필지(한 단지 여러 집)는 한 번만 묻기
        with httpx.Client(timeout=30, headers={"Accept": "application/json"}) as client:
            for i, (item_id, code, lot, usage, address) in enumerate(rows, 1):
                pnu = pnu_of(code, lot)
                if not pnu:
                    continue
                for kind in kinds_for(usage):
                    try:
                        got = cache.get((kind, pnu))
                        if got is None:
                            got = fetch(client, key, domain, kind, pnu, this_year)
                            if not got["items"]:  # 올해 공시 전이거나 없음 → 지난해
                                got = fetch(client, key, domain, kind, pnu, this_year - 1)
                            cache[(kind, pnu)] = got
                    except ApiError as e:
                        print(f"\n[멈춤] {kind} {pnu}: {e}\n  키·서비스(국가중점데이터)·하루 한도를 확인하세요. 받은 데까지 저장했어요.")
                        conn.commit()
                        raise SystemExit(1) from e
                    if a.probe:
                        print(f"--- {item_id} {usage.strip()} · {address} · {kind} · pnu {pnu} · {got['year']}년 {got['total']}건")
                        print(json.dumps(got["items"][:2], ensure_ascii=False, indent=1)[:2500])
                    if kind == "apt":
                        got = {**got, "items": pick_unit(got["items"], address)}
                        if a.probe:
                            print(f"    이 집으로 고른 줄: {len(got['items'])}건")
                    conn.execute(
                        """insert into raw.official_price_raw (item_id, kind, pnu, std_year, payload)
                           values (%s,%s,%s,%s,%s)
                           on conflict (item_id, kind) do update set pnu = excluded.pnu,
                             std_year = excluded.std_year, payload = excluded.payload, fetched_at = now()""",
                        (item_id, kind, pnu, got["year"], Jsonb(got)),
                    )
                job.count += 1
                if i % 50 == 0:
                    conn.commit()
                    print(f"  {i:,}/{len(rows):,}")
            conn.commit()
    print(f"끝: 물건 {job.count:,}건")


if __name__ == "__main__":
    main()
