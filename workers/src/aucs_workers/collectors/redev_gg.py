"""경기데이터드림 「일반 정비 사업 추진 현황」 → ref.redev_zones (분기 갱신, 11/16).

    uv run python -m aucs_workers.collectors.redev_gg

- 경기도 노후신도시정비과가 내는 자료(약 530구역): 시군 · 구역 이름 · 사업유형 · 단계 · 소재지 · 단계별 날짜 · 세대수.
- 준공 · 청산된 구역은 넣지 않음. source = '경기 정비사업' 줄을 통째로 갈아 끼움.
- 키: .env 의 GG_OPENAPI_KEY. 이주 0059(detail 칸)가 적용돼 있어야 함. 정비사업 목록(redev)을 받을 때 같이 돎.
- 조합원 자격 신호는 규제지역(기준표 regulated_areas)인 물건에만 뜸 — 규칙(risk)이 가름.
"""

import json
import os
import re
from datetime import date
from typing import Any

import httpx

from aucs_workers.collectors.redev_seoul import as_of
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

SOURCE = "경기 정비사업"
URL = "https://openapi.gg.go.kr/GenrlimprvBizpropls"
ENDED = ("준공", "청산")
DATES = {
    "designated": "IMPRV_ZONE_APPONT_FIRST_DE", "committee": "PROPLSN_COMMISN_APRV_DE",
    "union": "ASSOCTN_FOUND_CONFMTN_DE", "plan": "BIZ_IMPLMTN_CONFMTN_DE",
    "disposal": "MANAGE_DISPOSIT_CONFMTN_DE", "construction": "STRCONTR_DE",
}  # fmt: skip
_LOT = re.compile(r"([가-힣]+[0-9]*(?:동|가|리))\s*(?:산\s*)?(\d+)(?:-(\d+))?")


def _day(v: Any) -> str | None:
    """「20221227」 → 「2022-12-27」. 날짜가 아니면 None."""
    s = re.sub(r"\D", "", str(v or ""))
    if len(s) != 8:
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()
    except ValueError:
        return None


def _num(v: Any) -> int:
    s = str(v or "").replace(",", "").strip()
    return int(float(s)) if re.fullmatch(r"\d+(\.0+)?", s) else 0


def to_zone(r: dict[str, Any]) -> dict[str, Any] | None:
    """API 한 줄 → ref.redev_zones 한 줄 (순수 함수). 끝난 구역 · 이름 없는 줄은 None."""
    gu, name = str(r.get("SIGUN_NM") or "").strip(), str(r.get("IMPRV_ZONE_NM") or "").strip()
    stage = str(r.get("BIZ_STEP_NM") or "").strip()
    if not gu or not name or stage in ENDED:
        return None
    dates = {k: d for k, c in DATES.items() if (d := _day(r.get(c)))}
    sale = _num(r.get("ASOCNTMB_LOTOUT_HSHLD_CNT")) + _num(r.get("GENRL_LOTOUT_HSHLD_CNT"))
    homes = {
        k: v
        for k, v in (
            ("old", _num(r.get("EXISTNG_HOUSNG_HSHLD_CNT"))),
            ("new", _num(r.get("BIZ_IMPLMTN_HSHLD_CNT_TOTSUM"))),
            ("sale", sale),
            ("rent", _num(r.get("RENT_HSHLD_CNT"))),
        )
        if v > 0
    }
    detail = {k: v for k, v in (("dates", dates), ("homes", homes)) if v}
    addr = re.sub(r"\bnan\b", "", str(r.get("LOCPLC_ADDR") or "")).strip()
    m = _LOT.search(addr.replace(gu, "", 1))
    return {"gu": gu, "name": name, "biz_type": str(r.get("BIZ_TYPE_NM") or "").strip() or None,
            "stage": stage or None, "address": addr or None,
            "dong_name": m.group(1) if m else None, "main_no": int(m.group(2)) if m else None,
            "sub_no": int(m.group(3) or 0) if m else 0,
            "detail": json.dumps(detail, ensure_ascii=False) if detail else None}  # fmt: skip


def fetch(key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with httpx.Client(timeout=60) as c:
        page = 1
        while True:
            body = c.get(
                URL, params={"KEY": key, "Type": "json", "pIndex": page, "pSize": 1000}
            ).json()
            d = body.get("GenrlimprvBizpropls")
            if not d:
                msg = (body.get("RESULT") or {}).get("MESSAGE") or str(body)[:200]
                raise SystemExit(f"경기데이터드림 응답 오류: {msg.replace(key, '***')}")
            part = next((x["row"] for x in d if "row" in x), [])
            total = next((h["list_total_count"] for x in d if "head" in x for h in x["head"]
                          if "list_total_count" in h), 0)  # fmt: skip
            rows += part
            if not part or len(rows) >= int(total):
                return rows
            page += 1


def main(geo: bool = True) -> None:
    key = os.getenv("GG_OPENAPI_KEY", "").strip().strip("\"'")
    if not key:
        raise SystemExit("GG_OPENAPI_KEY 가 비어 있습니다 (.env)")
    got = fetch(key)
    zones = [z for r in got if (z := to_zone(r))]
    if len(got) < 300 or len(zones) < 150:
        raise SystemExit(
            f"{len(got)}줄 · 구역 {len(zones)}곳만 받음 — 자료 꼴이 바뀐 듯. 아무것도 바꾸지 않았어요."
        )
    with connect() as conn, run(conn, "redev_gg", "경기 정비사업") as job:
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
                " source_date, detail) values ('경기 정비사업', %(gu)s, %(name)s, %(biz_type)s, %(stage)s,"
                " %(address)s, %(dong_name)s, %(main_no)s, %(sub_no)s, %(base)s, %(detail)s::jsonb)",
                [{**z, "base": base} for z in zones],
            )
        job.count = len(zones)
    lot = sum(1 for z in zones if z["main_no"])
    print(
        f"끝: 자료 기준일 {base} · 받은 줄 {len(got):,} · 진행 중 구역 {len(zones):,}곳 · 대표지번 읽음 {lot:,}"
    )
    if geo and os.getenv("VWORLD_API_KEY", "").strip():
        import sys

        from aucs_workers.collectors import redev_geo

        sys.argv = sys.argv[:1]
        redev_geo.main()


if __name__ == "__main__":
    main()
