"""건축물대장(건축HUB 표제부·층별개요) — 진행 중인 경매 물건의 지번만 받아 core.building_register 에.

    uv run python -m aucs_workers.collectors.buildings              # 아침 묶음: 새 지번 위주 (기본 800곳)
    uv run python -m aucs_workers.collectors.buildings --cap 3000   # 처음 한 번 따라잡기
    uv run python -m aucs_workers.collectors.buildings --retry-none # 비었던 지번만 다시(새 지번도 같이)

- 관심 담긴 물건 → 매각기일 가까운 순. 같은 지번은 90일 안에 다시 받지 않음(비었거나 덜 받은 곳은 3일 뒤 다시).
- 층별개요는 근생빌라 판단이 필요한 주택류(아파트 빼고)만 — 큰 단지는 쪽수가 많아 하루 한도를 아낌.
- 공공데이터포털 하루 한도·인증 오류면 받은 데까지 저장하고 멈춤. 가끔 빈 응답 → 쉬었다 다시.
- 활용신청: 「국토교통부_건축HUB_건축물대장정보 서비스」(경매레이더와 같은 키).
"""

import argparse
import json
import os
import re
import time
from typing import Any
from urllib.parse import unquote

import httpx
import psycopg
from aucs_rules.building import parse_jibun
from psycopg.types.json import Jsonb

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

BASE = "https://apis.data.go.kr/1613000/BldRgstHubService"
OPS = {"title": "getBrTitleInfo", "floor": "getBrFlrOulnInfo"}
GAP = 0.2  # 초당 5회
ROWS = 100
LAND = ("전답", "임야", "대지", "자동차", "중기", "대지,임야,전답", "자동차,중기", "선박", "광업권")
FLOOR_USAGES = re.compile(r"(다세대|연립|빌라|다가구|단독|근린|상가)")


class ApiError(Exception):
    pass


class Incomplete(Exception):
    pass


def lot_key(plat: str, bun: str, ji: str) -> str:
    return f"{'산' if plat == '1' else ''}{bun}-{ji}"


def fetch(client: httpx.Client, key: str, op: str, code10: str, plat: str, bun: str, ji: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page, total = 1, 0
    params = {"serviceKey": key, "sigunguCd": code10[:5], "bjdongCd": code10[5:], "platGbCd": plat,
              "bun": bun, "ji": ji, "numOfRows": ROWS, "_type": "json"}  # fmt: skip
    while True:
        body, status = "", 0
        for attempt in range(5):
            time.sleep(GAP)
            try:
                r = client.get(f"{BASE}/{op}", params={**params, "pageNo": page})
                body, status = (r.text or "").strip(), r.status_code
            except httpx.HTTPError:
                body = ""
            if "초당" in body or "PER_SECOND" in body or not body:
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        if not body:
            if status and status != 200:
                raise ApiError(f"빈 응답 (HTTP {status})")
            if out and len(out) < total:
                raise Incomplete(f"{op} {len(out)}/{total}")
            return out  # 첫 쪽부터 계속 비면 자료 없음
        if body.startswith("<"):
            msg = re.search(r"<(?:returnAuthMsg|resultMsg|errMsg)>([^<]+)", body)
            raise ApiError(msg.group(1) if msg else body[:120])
        d = json.loads(body)
        resp = d.get("response", {})
        code = str(resp.get("header", {}).get("resultCode", "00"))
        if code not in ("00", "000", "0"):
            raise ApiError(f"{code} {resp.get('header', {}).get('resultMsg', '')}")
        b = resp.get("body") or {}
        total = int(b.get("totalCount") or 0)
        its = b.get("items")
        part = (its.get("item") or []) if isinstance(its, dict) else []
        out += [part] if isinstance(part, dict) else part
        if page * ROWS >= total or not part:
            return out
        page += 1


TARGETS_SQL = """
with t as (
  select i.item_id, i.region_code, i.lot_no, i.usage_name, i.sale_date,
         exists (select 1 from app.watch_items w where w.item_id = i.item_id) as watched
  from core.items i
  where i.sale_date >= current_date and i.status_code is distinct from 'gone'
    and length(i.region_code) = 10 and coalesce(i.lot_no, '') <> ''
    and coalesce(i.usage_name, '') <> all(%(land)s)
)
select region_code, lot_no, bool_or(usage_name ~ %(floor_re)s) as want_floor,
       bool_or(watched) as watched, min(sale_date) as first_date, array_agg(item_id) as items
from t group by 1, 2
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=800, help="한 번에 받을 최대 지번 수")
    ap.add_argument("--retry-none", action="store_true", help="비었던 지번을 날짜와 상관없이 다시")
    a = ap.parse_args()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 가 비어 있습니다 (.env)")
    with connect() as conn, run(conn, "buildings", "건축물대장") as job:
        rows = conn.execute(
            TARGETS_SQL, {"land": list(LAND), "floor_re": FLOOR_USAGES.pattern}
        ).fetchall()
        done = {
            (r[0], r[1]): (r[2], r[3])
            for r in conn.execute(
                "select region_code, lot_no, result, extract(epoch from now() - last_at) / 86400 from core.building_fetch"
            ).fetchall()
        }
        # 같은 지번(「1-2」와 「1-2^3」 등)은 하나로 모음
        lots: dict[tuple[str, str], dict[str, Any]] = {}
        for code, lot, want_floor, watched, first_date, items in rows:
            p = parse_jibun(lot)
            if not p:
                continue
            g = lots.setdefault((code, lot_key(*p)), {"p": p, "floor": False, "watched": False,
                                                      "first": first_date, "items": []})  # fmt: skip
            g["floor"] |= bool(want_floor)
            g["watched"] |= bool(watched)
            g["first"] = min(g["first"], first_date)
            g["items"] += items
        todo = []
        for (code, lk), g in lots.items():
            prev = done.get((code, lk))
            again = prev and prev[0] in ("none", "partial") and (a.retry_none or prev[1] >= 3)
            if prev and not (prev[1] >= 90 or again):
                continue
            todo.append((not g["watched"], g["first"], code, lk, g))
        todo.sort(key=lambda x: (x[0], x[1]))
        todo = todo[: a.cap]
        print(f"[시작] 지번 {len(todo):,}곳 (전체 대상 {len(lots):,}곳)")
        retry: list[tuple[str, str, dict[str, Any]]] = []
        with httpx.Client(timeout=30, follow_redirects=True, headers={"Accept": "application/json"}) as client:
            for i, (_, _, code, lk, g) in enumerate(todo, 1):
                got: dict[str, list[dict[str, Any]]] = {}
                partial = False
                try:
                    for kind, op in OPS.items():
                        if kind == "floor" and not g["floor"]:
                            continue
                        try:
                            got[kind] = fetch(client, key, op, code, *g["p"])
                        except Incomplete:
                            partial = True
                except ApiError as e:
                    print(f"\n[멈춤] {e} — 활용신청·하루 한도를 확인하세요. 받은 데까지 저장했어요.")
                    conn.commit()
                    raise
                if not got.get("title") and not partial:
                    retry.append((code, lk, g))  # 표제부가 비면 끝에서 한 번 더(건축HUB 가 가끔 빈 결과를 줌)
                save(conn, code, lk, got, partial, g["items"])
                job.count += 1
                if i % 50 == 0:
                    conn.commit()
                    print(f"  {i:,}/{len(todo):,}")
            conn.commit()
            # 두 번째: 비었던 곳을 천천히 다시(새 연결) — 다시 받아지면 「일시적으로 빈 결과」였던 것
            found = 0
            if retry:
                print(f"  빈 곳 {len(retry):,}곳 다시")
                with httpx.Client(timeout=30, follow_redirects=True, headers={"Accept": "application/json"}) as c2:
                    for code, lk, g in retry:
                        time.sleep(0.8)
                        got = {}
                        try:
                            for kind, op in OPS.items():
                                if kind == "floor" and not g["floor"]:
                                    continue
                                got[kind] = fetch(c2, key, op, code, *g["p"])
                        except Incomplete:
                            continue
                        except ApiError as e:
                            print(f"  [다시 받기 멈춤] {e}")
                            break
                        if got.get("title"):
                            found += 1
                            save(conn, code, lk, got, False, g["items"])
                    conn.commit()
                print(f"  다시 받아 채운 곳 {found:,}/{len(retry):,}")
        conn.commit()
    print(f"끝: 지번 {job.count:,}곳")


def save(
    conn: psycopg.Connection,
    code: str,
    lk: str,
    got: dict[str, list[dict[str, Any]]],
    partial: bool,
    item_ids: list[str],
) -> None:
    for kind, items in got.items():
        conn.execute(
            "delete from core.building_register where region_code = %s and lot_no = %s and kind = %s",
            (code, lk, kind),
        )
        with conn.cursor() as cur:
            cur.executemany(
                "insert into core.building_register (region_code, lot_no, kind, seq, data) values (%s,%s,%s,%s,%s)",
                [(code, lk, kind, n, Jsonb(x)) for n, x in enumerate(items)],
            )
    nt, nf = len(got.get("title", [])), len(got.get("floor", []))
    result = "partial" if partial else ("ok" if nt else "none")
    conn.execute(
        """insert into core.building_fetch (region_code, lot_no, last_at, result, titles, floors)
           values (%s, %s, now(), %s, %s, %s)
           on conflict (region_code, lot_no) do update set last_at = now(), result = excluded.result,
             titles = excluded.titles, floors = excluded.floors""",
        (code, lk, result, nt, nf),
    )
    # 이 지번의 물건들은 다시 분석되도록(아침 묶음 analyze --stale)
    conn.execute("update core.items set updated_at = now() where item_id = any(%s)", (item_ids,))


if __name__ == "__main__":
    main()
