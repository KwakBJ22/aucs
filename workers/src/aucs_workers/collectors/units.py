"""건축물대장 전유공용면적 — 진행 중인 경매 물건의 「호」 줄만 받아 core.building_units 에(11/16).

    uv run python -m aucs_workers.collectors.units             # 아침 묶음: 하루 1,200건
    uv run python -m aucs_workers.collectors.units --cap 50    # 조금만

- 지번 + hoNm 으로 그 호만 받음. 호 이름 꼴이 대장마다 달라 차례로 시도: 「416」 → 「416호」 → 「제416호」
  → 글자 붙은 꼴(A303 · B102) → 지하(B101) → 「3층301호」(11/16 표본 40건 중 35건 맞음, logs/probe_units.log).
- 한 지번에 동이 여럿이면 물건의 동(「103동」 · 「비동」)으로 거름.
- 관심 담긴 물건 → 매각기일 가까운 순. 받은 물건은 90일 안에 다시 안 받음(못 찾은 것은 14일 뒤 한 번 더).
- 공공데이터포털 하루 한도 · 인증 오류면 받은 데까지 저장하고 멈춤.
"""

import argparse
import os
import re
from typing import Any
from urllib.parse import unquote

import httpx
import psycopg
from aucs_rules.building import parse_jibun
from psycopg.types.json import Jsonb

from aucs_workers.collectors.buildings import ApiError, Incomplete, fetch
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

OP = "getBrExposPubuseAreaInfo"
LETTER = {"에이": "A", "비": "B", "씨": "C", "디": "D", "와이": "Y"}
# 지하 호(11/18): 「지하층101호」 · 「지1층비122호」 · 「제지하2층 제비201호」 — 예전엔 숫자만으로 먼저 찾아 지상 같은 번호 호를
# 잘못 잡았음(11건). 「22층비2210호」의 「비」는 지하가 아니라 글자(B동 · B호)라 층 글자로만 가림.
UNDER = r"지하|지층|지\s*\d+\s*층"

TARGETS_SQL = """
select i.item_id, i.region_code, i.lot_no, i.building_desc
from core.items i
left join core.building_units u on u.item_id = i.item_id
where to_regclass('core.building_units') is not null
  and i.sale_date >= current_date and i.status_code is distinct from 'gone'
  and length(i.region_code) = 10 and coalesce(i.lot_no, '') <> ''
  and i.building_desc ~ '[0-9]+\\s*호'
  and (u.item_id is null
       or (u.result = 'ok' and u.fetched_at < now() - interval '90 days')
       or (u.result = 'none' and u.fetched_at < now() - interval '14 days')
       -- 11/18: 지하 호인데 지상 호를 잡아 둔 것은 다시 받음
       or (u.result = 'ok' and i.building_desc ~ '(지하|지층|지 *[0-9]+ *층)'
           and not exists (select 1 from jsonb_array_elements(coalesce(u.rows, '[]'::jsonb)) r
                           where r->>'exposPubuseGbCdNm' = '전유' and r->>'flrGbCdNm' = '지하')))
order by not exists (select 1 from app.watch_items w where w.item_id = i.item_id), i.sale_date, i.item_id
limit %(cap)s
"""


def ho_names(desc: str) -> tuple[list[str], str | None]:
    """물건 설명에서 대장 호 이름 후보(차례대로)와 동(「103」 · 「비」)."""
    ho = re.search(r"([A-Za-z]?\d+)\s*호", desc)
    if not ho:
        return [], None
    n = ho.group(1)
    dong = re.search(r"(\d+|[가-힣A-Za-z])동[\s\-]", desc)  # 「201동-803호」도(11/18)
    floor = re.search(r"(\d+)\s*층\s*제?\s*" + re.escape(n) + r"\s*호", desc)
    letter = re.search(r"(에이|비|씨|디|와이)\s*-?\s*\d+\s*호", desc)  # 「디-520호」도(11/18)
    pre = LETTER.get(letter.group(1), "") if letter else ""
    under = is_under(desc)
    plain = [n, n + "호", "제" + n + "호"]
    if under:  # 지하면 B 붙은 꼴부터(숫자만 먼저 찾으면 지상 같은 번호를 잡음)
        names = ["B" + n, "B" + n + "호", "비" + n + "호", "지하" + n + "호", *plain]
    elif pre:  # 글자 붙은 호(A303 · B-102)는 글자 꼴부터
        names = [pre + n, pre + n + "호", pre + "-" + n, pre + "-" + n + "호", *plain]
    else:
        names = plain
    if floor:
        names.append(f"{floor.group(1)}층{n}호")
    seen: list[str] = []
    for x in names:
        if x not in seen:
            seen.append(x)
    return seen, dong.group(1) if dong else None


def is_under(desc: str) -> bool:
    return bool(re.search(UNDER, desc))


def found(rows: list[dict[str, Any]], under: bool) -> bool:
    """그 호의 전유 줄이 있나. 지하 호면 전유 줄이 지하여야 함(11/18)."""
    return any(
        r.get("exposPubuseGbCdNm") == "전유" and (not under or r.get("flrGbCdNm") == "지하")
        for r in rows
    )


def pick(rows: list[dict[str, Any]], dong: str | None) -> list[dict[str, Any]]:
    """동이 여럿이면 물건의 동만. 「비」 동은 「B동」 · 「비동」 둘 다."""
    rows = [r for r in rows if "hoNm" in r]
    dongs = {str(r.get("dongNm") or "").strip() for r in rows}
    if not dong or len(dongs) <= 1:
        return rows
    keys = {dong, LETTER.get(dong, dong)}
    return [r for r in rows if any(k in str(r.get("dongNm") or "") for k in keys)]


def num(x: Any) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def save(
    conn: psycopg.Connection, item_id: str, code: str, lot: str, name: str | None, rows: list
) -> None:
    own = [r for r in rows if r.get("exposPubuseGbCdNm") == "전유"]
    com = [r for r in rows if r.get("exposPubuseGbCdNm") == "공용"]
    first = own[0] if own else {}
    conn.execute(
        """insert into core.building_units (item_id, region_code, lot_no, ho_name, result, own_area,
             common_area, own_use, own_use_etc, rows, fetched_at)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
           on conflict (item_id) do update set region_code = excluded.region_code,
             lot_no = excluded.lot_no, ho_name = excluded.ho_name, result = excluded.result,
             own_area = excluded.own_area, common_area = excluded.common_area,
             own_use = excluded.own_use, own_use_etc = excluded.own_use_etc, rows = excluded.rows,
             fetched_at = now()""",
        (
            item_id, code, lot, name, "ok" if own else "none",
            round(sum(num(r.get("area")) for r in own), 4) if own else None,
            round(sum(num(r.get("area")) for r in com), 4) if com else None,
            first.get("mainPurpsCdNm"), first.get("etcPurps"), Jsonb(rows),
        ),
    )  # fmt: skip
    if own:  # 다음 분석 때 다시 보도록(analyze --stale)
        conn.execute("update core.items set updated_at = now() where item_id = %s", (item_id,))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=1200, help="한 번에 받을 최대 물건 수")
    a = ap.parse_args()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 가 비어 있습니다 (.env)")
    with connect() as conn:
        if not conn.execute("select to_regclass('core.building_units')").fetchone()[0]:
            print("core.building_units 가 아직 없음(이주 0061 적용 전) — 건너뜀")
            return
        with run(conn, "units", "건축물대장 전유공용면적") as job:
            todo = conn.execute(TARGETS_SQL, {"cap": a.cap}).fetchall()
            print(f"[시작] 물건 {len(todo):,}건")
            hit = 0
            with httpx.Client(
                timeout=30, follow_redirects=True, headers={"Accept": "application/json"}
            ) as client:
                for i, (item_id, code, lot, desc) in enumerate(todo, 1):
                    p = parse_jibun(lot)
                    names, dong = ho_names(desc or "")
                    rows: list[dict[str, Any]] = []
                    used = None
                    if p and names:
                        for name in names:
                            try:
                                got = fetch(client, key, OP, code, *p, extra={"hoNm": name})
                            except Incomplete:
                                got = []
                            except ApiError as e:
                                print(f"\n[멈춤] {e} — 하루 한도 · 활용신청을 확인하세요. 받은 데까지 저장했어요.")  # fmt: skip
                                conn.commit()
                                raise
                            rows = pick(got, dong)
                            if found(rows, is_under(desc or "")):
                                used = name
                                break
                    save(conn, item_id, code, lot, used, rows if used else [])
                    hit += bool(used)
                    job.count += 1
                    if i % 50 == 0:
                        conn.commit()
                        print(f"  {i:,}/{len(todo):,} (찾음 {hit:,})")
            conn.commit()
    print(f"끝: 물건 {job.count:,}건 · 호 찾음 {hit:,}건")


if __name__ == "__main__":
    main()
