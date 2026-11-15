"""정비구역 단계별 날짜(11/15 대표님 — 파일의 날짜를 실제로 쓰자).

서울시 「정비사업 추진현황」 파일(재개발 · 재건축 496구역, 강사에게 받은 것 — D:\Auction\data\기준표)에는 구역마다
구역지정 · 추진위 · 조합설립인가 · 건축심의 · 사업시행인가 · 관리처분인가 · 이주 · 착공 날짜가 있는데, 10/17 에는
지금 단계 이름만 옮겼음. 이 날짜를 db/seed/redev_stage_dates.json 으로 뽑아 두면 분석(redev_match)이 구역에 붙이고,
조합원 자격(REDEV-01)과 상세 화면이 씀. DB 는 건드리지 않음.

    cd D:\Auction\auction-platform\workers
    uv run python -m aucs_workers.collectors.redev_dates "D:\Auction\data\기준표\★(26년 6월기준) 서울시 정비사업 추진현황.xlsx"

- 새 파일을 받으면 다시 돌리고, 규칙 버전(ENGINE_VERSION)을 올려야 물건마다 다시 분석돼 화면에 나옴.
- 기준일은 파일 이름의 「(26년 6월기준)」에서(그 달 말일). --as-of 2026-06-30 으로 따로 줄 수 있음.
"""

import argparse
import calendar
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from aucs_workers.collectors.station_official import xlsx_rows
from aucs_workers.db import ROOT

SEED = ROOT / "db" / "seed" / "redev_stage_dates.json"
# 파일 칸(26년 6월 판): C 자치구 · D 구역명 · G 공공/민간 · H 일반/재촉 · K 기존 가구수 · L~W 단계 날짜 · X~Z 건립 세대수
DATE_COLS = {
    "L": "designated", "M": "designated_changed", "N": "committee", "O": "union", "P": "review",
    "Q": "plan", "R": "plan_changed", "S": "disposal", "T": "disposal_changed", "U": "move_start",
    "V": "move_end", "W": "construction",
}  # fmt: skip
NUM_COLS = {"K": "homes_old", "X": "homes_new", "Y": "homes_sale", "Z": "homes_rent"}


def to_date(v: str | None) -> str | None:
    """엑셀 칸 값 → 'YYYY-MM-DD'(일련번호 · 글자 날짜). 날짜가 아니면 None."""
    s = (v or "").strip()
    if re.fullmatch(r"\d{5}(\.\d+)?", s) and 20000 < float(s) < 60000:
        return (date(1899, 12, 30) + timedelta(days=int(float(s)))).isoformat()
    m = re.match(r"(\d{4})[-./]\s*(\d{1,2})[-./]\s*(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    return None


def as_of_from(name: str) -> str | None:
    """「(26년 6월기준)」 → 2026-06-30."""
    m = re.search(r"(\d{2})년\s*(\d{1,2})월\s*기준", name)
    if not m:
        return None
    y, mo = 2000 + int(m.group(1)), int(m.group(2))
    return date(y, mo, calendar.monthrange(y, mo)[1]).isoformat()


def zones(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """파일 줄 → {「자치구|구역명」: {단계 날짜 …, homes_*, public, kind}}. 자료 줄은 A 칸이 숫자."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not (r.get("A") or "").strip().isdigit() or not r.get("C") or not r.get("D"):
            continue
        z: dict[str, Any] = {k: d for c, k in DATE_COLS.items() if (d := to_date(r.get(c)))}
        for c, k in NUM_COLS.items():
            if re.fullmatch(r"\d+(\.0+)?", (r.get(c) or "").strip()) and float(r[c]) > 0:
                z[k] = int(float(r[c]))
        if r.get("G"):
            z["public"] = r["G"].strip()
        if r.get("H"):
            z["kind"] = r["H"].strip()
        out[f"{r['C'].strip()}|{r['D'].strip()}"] = z
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--as-of", help="자료 기준일(YYYY-MM-DD) — 없으면 파일 이름에서")
    a = ap.parse_args()
    f = Path(a.file)
    z = zones(xlsx_rows(f.read_bytes()))
    if len(z) < 300:
        raise SystemExit(f"구역을 {len(z)}곳만 읽음 — 파일 꼴이 바뀐 듯. 아무것도 쓰지 않았어요.")
    as_of = a.as_of or as_of_from(f.name)
    SEED.write_text(
        json.dumps(
            {"as_of": as_of, "file": f.name, "zones": z},
            ensure_ascii=False,
            indent=0,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    n = {k: sum(1 for v in z.values() if k in v) for k in DATE_COLS.values()}
    print(f"구역 {len(z)}곳 · 기준일 {as_of} → {SEED}")
    print("  날짜 있는 구역: " + " · ".join(f"{k} {v}" for k, v in n.items()))


if __name__ == "__main__":
    main()
