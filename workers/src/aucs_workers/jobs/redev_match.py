"""경매 물건 ↔ 서울 정비사업(정보몽땅) 잇기.

구역 경계 자료가 없어 두 가지만 확실하게 봅니다.
1) 대표지번이 물건 지번과 같음(같은 구·동)
2) 재건축·리모델링 단지 이름이 물건 건물 이름에 들어 있음(같은 구·동, 이름 3글자 이상)
구역 안 다른 지번은 못 잡습니다 — 토지이용계획(vworld)을 붙이면 보완.
"""

import json
import re
from functools import lru_cache
from typing import Any

from aucs_rules.location import ZONE_ADDRESS_SQL, ZONE_GUESS_M, zone_usable
from aucs_rules.redev_member import zone_kind

from aucs_workers.db import ROOT

_SEED = ROOT / "db" / "seed" / "redev_stage_dates.json"
# 구역에 붙이는 단계 날짜(11/15) — 바뀐 날(…_changed) · 세대수는 안 붙임
_DATE_KEYS = ("designated", "committee", "union", "review", "plan", "disposal", "move_start",
              "move_end", "construction")  # fmt: skip

_STRIP = re.compile(
    r"\s|\(.*?\)|아파트.*$|주택재건축.*$|재건축.*$|정비사업.*$|조합.*$|리모델링.*$|추진위.*$"
)


def zone_key(name: str) -> str | None:
    """단지 이름 열쇠: 「뉴서울아파트, 개나리 … 재건축정비사업」 → 「뉴서울」."""
    k = _STRIP.sub("", name.split(",")[0])
    k = re.sub(r"[0-9]+차$", "", k)
    if len(k) < 3 or re.search(r"(구|역)$", k) or re.search(r"[0-9]", k):
        return None
    return k


@lru_cache(maxsize=1)
def stage_dates() -> tuple[str | None, dict[str, dict[str, Any]]]:
    """서울시 정비사업 추진현황의 단계 날짜(collectors/redev_dates 가 뽑아 둔 것) → (기준일, {「구|구역명」: 날짜})."""
    try:
        d = json.loads(_SEED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, {}
    return d.get("as_of"), {k.replace(" ", ""): v for k, v in (d.get("zones") or {}).items()}


def with_dates(z: dict[str, Any], gu: str | None, names: list[str | None]) -> dict[str, Any]:
    """구역에 단계 날짜를 붙임 — 이름이 같은 구역, 없으면 같은 대표지번의 다른 이름. 없으면 그대로."""
    as_of, by = stage_dates()
    for name in names:
        d = by.get(f"{gu}|{name}".replace(" ", "")) if gu and name else None
        dates = {k: d[k] for k in _DATE_KEYS if d.get(k)} if d else None
        if dates:
            return {**z, "dates": dates, "dates_as_of": as_of}
    return z


def dong_of(address: str | None) -> str | None:
    m = re.search(r"\s([가-힣0-9]+동[0-9]*가?)\s", address or "")
    return m.group(1) if m else None


def lot_parts(lot_no: str | None) -> tuple[int, int] | None:
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", (lot_no or "").strip())
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


def usable(z: dict[str, Any]) -> bool:
    return zone_usable(z.get("stage"), z.get("biz_type"))  # 판단은 규칙 한 곳(LOC-01, 11/13)


def pick(item: dict[str, Any], zones: list[dict[str, Any]]) -> dict[str, Any] | None:
    """같은 구·동 정비사업 목록에서 물건과 맞는 것 하나 (순수 함수)."""
    lot = lot_parts(item.get("lot_no"))
    bname = re.sub(r"\s", "", item.get("building_desc") or "")
    for z in zones:
        if not usable(z):
            continue
        if lot and (z.get("main_no"), z.get("sub_no") or 0) == lot:
            return {**z, "how": "지번"}
    for z in zones:
        if not usable(z) or not re.search("재건축|리모델링", z.get("biz_type") or ""):
            continue
        k = zone_key(z["name"])
        if (
            k and k != z.get("dong_name") and k in bname
        ):  # 「역삼동」 같은 동 이름은 단지 이름이 아님
            return {**z, "how": "단지 이름"}
    return None


def load_zones(conn: Any) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """서울 정비구역 전부를 (구, 동)으로 묶어 한 번에(11/14) — 분석이 물건마다 묻지 않게. 줄 순서는 find_zone 과 같음."""
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in conn.execute(
        """select gu, dong_name, name, biz_type, stage, main_no, sub_no from ref.redev_zones
           order by source = '사업장 목록' desc, zone_id"""
    ).fetchall():
        gu, dong, name, biz, stage, main_no, sub_no = (
            (r[k] for k in ("gu", "dong_name", "name", "biz_type", "stage", "main_no", "sub_no"))
            if isinstance(r, dict)
            else r
        )
        out.setdefault((gu, dong), []).append(
            {
                "name": name,
                "biz_type": biz,
                "stage": stage,
                "main_no": main_no,
                "sub_no": sub_no,
                "dong_name": dong,
            }  # fmt: skip
        )
    return out


def find_zone(
    cur: Any,
    item: dict[str, Any],
    zones_by: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
) -> dict[str, Any] | None:
    if item.get("sido") != "서울특별시":
        return None
    dong = dong_of(item.get("address"))
    if not dong:
        return None
    if zones_by is not None:
        rows: list[Any] = zones_by.get((item.get("sigungu") or "", dong), [])
    else:
        rows = cur.execute(
            """select name, biz_type, stage, main_no, sub_no, dong_name from ref.redev_zones
               where gu = %s and dong_name = %s order by source = '사업장 목록' desc, zone_id""",
            (item.get("sigungu"), dong),
        ).fetchall()
    zones = [
        r
        if isinstance(r, dict)
        else dict(
            zip(("name", "biz_type", "stage", "main_no", "sub_no", "dong_name"), r, strict=True)
        )
        for r in rows
    ]
    z = pick(item, zones)
    if not z:
        return None
    out = {k: z.get(k) for k in ("name", "biz_type", "stage", "how")}
    lot = (z.get("main_no"), z.get("sub_no") or 0)
    same = [x["name"] for x in zones if lot[0] and (x.get("main_no"), x.get("sub_no") or 0) == lot]
    return with_dates(out, item.get("sigungu"), [z.get("name"), *same])


def near_zone(cur: Any, item_id: str) -> dict[str, Any] | None:
    """토지 이용 계획이 「정비구역」인 물건에 어느 구역인지 잇기(11/14): 대표지번이 가장 가까운(500m 안)
    재개발 · 재건축 구역. 구역 경계가 아니라 「아마 이 구역」 — how 에 그렇게 적음."""
    rows = cur.execute(
        f"""select z.name, z.biz_type, z.stage, round(st_distance(p.geom, i.geom))::int as m, z.gu
            from core.items i
            join ref.place_points p on p.geom is not null and i.geom is not null
             and st_dwithin(p.geom, i.geom, {ZONE_GUESS_M})
            join ref.redev_zones z on {ZONE_ADDRESS_SQL} = p.address
            where i.item_id = %s
            order by m, z.source = '사업장 목록' desc limit 20""",
        (item_id,),
    ).fetchall()
    for r in rows:
        z = (
            r
            if isinstance(r, dict)
            else dict(zip(("name", "biz_type", "stage", "m", "gu"), r, strict=False))
        )
        if zone_usable(z.get("stage"), z.get("biz_type")) and zone_kind(z.get("biz_type")):
            out = {"name": z["name"], "biz_type": z["biz_type"], "stage": z["stage"],
                   "how": f"토지 이용 계획 · 가까운 구역(약 {z['m']}m)"}  # fmt: skip
            return with_dates(out, z.get("gu"), [z["name"]])
    return None
