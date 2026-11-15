"""서울 열린데이터광장 「서울특별시 도시정비사업 통계」(OA-22856) → ref.redev_zones (분기 갱신, 11/15).

    uv run python -m aucs_workers.collectors.redev_seoul

- 구역마다 대표지번 · 단계 · 단계별 날짜 · 세대수가 있음(약 500구역). source = '도시정비사업 통계' 줄을 통째로 갈아 끼움.
- 키: .env 의 SEOUL_OPENAPI_KEY. 이주 0059(detail 칸)가 적용돼 있어야 함.
- 정비사업 목록(redev)을 받을 때 같이 돎. 따로 돌리면 끝에 새 대표지번 좌표(redev_geo)도 받음.
"""

import calendar
import json
import os
import re
from datetime import date
from typing import Any

import httpx

from aucs_workers.collectors.redev import split_lot
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

SOURCE = "도시정비사업 통계"
URL = "http://openapi.seoul.go.kr:8088/{key}/json/TbSeoulRedevStatus/{a}/{b}/"
PAGE = 1000
DATES = {
    "designated": "ZONE_DESIGNATION_INIT_YMD",
    "committee": "PROMOTION_COMMITTEE_YMD",
    "union": "ASSOCIATION_ESTABLISHMENT_YMD",
    "review": "ARCHITECTURAL_REVIEW_YMD",
    "plan": "BIZ_IMPLEMENTATION_INIT_YMD",
    "disposal": "MGMT_DISPOSITION_INIT_YMD",
    "move_start": "MIGRATION_START_YMD",
    "move_end": "MIGRATION_END_YMD",
    "construction": "CONSTRUCTION_START_YMD",
}  # fmt: skip  — 사업시행 · 관리처분은 최초 인가일(조합원 자격의 2018. 1. 25. 기준이 최초 인가)
HOMES = {"old": "EXISTING_HOUSEHOLDS", "new": "TOT_BUILT_HOUSEHOLDS",
         "sale": "SALE_BUILT_HOUSEHOLDS", "rent": "RENT_BUILT_HOUSEHOLDS"}  # fmt: skip
_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def to_zone(r: dict[str, Any]) -> dict[str, Any] | None:
    """API 한 줄 → ref.redev_zones 한 줄 (순수 함수). 구 · 구역명이 없으면 None."""
    gu, name = str(r.get("DISTRICT") or "").strip(), str(r.get("ZONE_NM") or "").strip()
    if not gu or not name:
        return None
    dates = {
        k: m.group(0) for k, c in DATES.items() if (m := _DAY.match(str(r.get(c) or "").strip()))
    }
    homes = {}
    for k, c in HOMES.items():
        v = str(r.get(c) or "").strip().replace(",", "")
        if re.fullmatch(r"\d+(\.0+)?", v) and float(v) > 0:
            homes[k] = int(float(v))
    detail = {k: v for k, v in (("dates", dates), ("homes", homes)) if v}
    addr = str(r.get("JIBUN_ADDR") or "").strip()
    dong, main_no, sub_no = split_lot(addr)
    return {"gu": gu, "name": name, "biz_type": str(r.get("BIZ_TYPE") or "").strip() or None,
            "stage": str(r.get("BIZ_STAGE") or "").strip() or None, "address": addr or None,
            "dong_name": dong, "main_no": main_no, "sub_no": sub_no,
            "detail": json.dumps(detail, ensure_ascii=False) if detail else None}  # fmt: skip


def as_of(zones: list[dict[str, Any]], today: date) -> date:
    """자료 기준일(순수 함수): 서울시가 「○○년 ○월 기준」으로 분기마다 내는 자료라, 들어 있는 날짜 가운데
    가장 늦은 날이 속한 분기의 끝날로 봄(26년 6월 기준 자료 → 2026-06-30). 못 가리면 받은 날."""
    days = [
        v
        for z in zones
        if z["detail"]
        for k, v in (json.loads(z["detail"]).get("dates") or {}).items()
        if not k.startswith("move_")  # 이주 시작 · 종료는 앞날의 예정일이 섞여 있어 뺌
    ]
    last = max((d for d in days if d <= today.isoformat()), default=None)
    if not last:
        return today
    y, m = int(last[:4]), int(last[5:7])
    q = (m - 1) // 3 * 3 + 3
    return date(y, q, calendar.monthrange(y, q)[1])


def fetch(key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with httpx.Client(timeout=60) as c:
        a = 1
        while True:
            body = c.get(URL.format(key=key, a=a, b=a + PAGE - 1)).json()
            d = body.get("TbSeoulRedevStatus")
            if not d:
                msg = (body.get("RESULT") or {}).get("MESSAGE") or str(body)[:200]
                raise SystemExit(f"서울 열린데이터광장 응답 오류: {msg.replace(key, '***')}")
            rows += d.get("row") or []
            if a + PAGE > int(d.get("list_total_count") or 0):
                return rows
            a += PAGE


def main(geo: bool = True) -> None:
    key = os.getenv("SEOUL_OPENAPI_KEY", "").strip().strip("\"'")
    if not key:
        raise SystemExit("SEOUL_OPENAPI_KEY 가 비어 있습니다 (.env)")
    zones = [z for r in fetch(key) if (z := to_zone(r))]
    if len(zones) < 300:
        raise SystemExit(
            f"구역을 {len(zones)}곳만 받음 — 자료 꼴이 바뀐 듯. 아무것도 바꾸지 않았어요."
        )
    with connect() as conn, run(conn, "redev_seoul", "서울 도시정비사업 통계") as job:
        if not conn.execute(
            "select 1 from information_schema.columns where table_schema = 'ref'"
            " and table_name = 'redev_zones' and column_name = 'detail'"
        ).fetchone():
            raise SystemExit(
                "ref.redev_zones 에 detail 칸이 없습니다 — 이주 0059 를 먼저 적용하세요."
            )
        base = as_of(zones, date.today())
        conn.execute("delete from ref.redev_zones where source = %s", (SOURCE,))
        with conn.cursor() as cur:
            cur.executemany(
                "insert into ref.redev_zones (source, gu, name, biz_type, stage, address, dong_name, main_no, sub_no,"
                " source_date, detail) values ('도시정비사업 통계', %(gu)s, %(name)s, %(biz_type)s, %(stage)s,"
                " %(address)s, %(dong_name)s, %(main_no)s, %(sub_no)s, %(base)s, %(detail)s::jsonb)",
                [{**z, "base": base} for z in zones],
            )
        job.count = len(zones)
    n = sum(1 for z in zones if z["detail"])
    lot = sum(1 for z in zones if z["main_no"])
    print(
        f"끝: 자료 기준일 {base} · 구역 {len(zones):,}곳 · 날짜나 세대수 있음 {n:,} · 대표지번 읽음 {lot:,}"
    )
    if geo and os.getenv("VWORLD_API_KEY", "").strip():
        import sys

        from aucs_workers.collectors import redev_geo

        sys.argv = sys.argv[:1]
        redev_geo.main()


if __name__ == "__main__":
    main()
