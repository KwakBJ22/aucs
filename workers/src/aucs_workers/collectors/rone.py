"""한국부동산원 R-ONE 통계 → ref.region_stats (가장 최근 시점만, 11/15).

    uv run python -m aucs_workers.collectors.rone

- 받는 것: 집합 상가 소득수익률 · 공실률(분기), 오피스텔 수익률 · 전월세전환율(월), 주택 전월세전환율(월 — 아파트 · 연립다세대 · 단독).
- 통계마다 가장 최근 시점을 찾아(이번 달부터 거꾸로) 그 시점 줄만 통째로 갈아 끼움. 요청은 통계마다 몇 번뿐.
- 키: .env 의 RONE_API_KEY. 이주 0060(ref.region_stats)이 적용돼 있어야 함. 실거래(trades) 받을 때 같이 돎(매월).
"""

import os
import sys
import time
from datetime import date
from typing import Any

import httpx

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
GAP = 1.0
# 통계 이름 → (통계표, 주기, 항목 이름에 들어 있어야 할 글, 지역을 읽는 칸)
TABLES: dict[str, tuple[str, str, str, str]] = {
    "shop_yield": ("T265693143819594", "QY", "소득수익률", "CLS_FULLNM"),
    "shop_vacancy": ("T267763143643502", "QY", "공실률", "CLS_FULLNM"),
    "officetel_yield": ("T245503133561624", "MM", "수익률", "GRP_NM"),
    "officetel_conv": ("T241163133546529", "MM", "전환율", "GRP_NM"),
    "conv_apt": ("A_2024_00156", "MM", "전환율", "CLS_FULLNM"),
    "conv_row": ("A_2024_00157", "MM", "전환율", "CLS_FULLNM"),
    "conv_house": ("A_2024_00158", "MM", "전환율", "CLS_FULLNM"),
}


def periods(cycle: str, today: date, n: int = 9) -> list[str]:
    """가장 최근부터 거꾸로 시점 n개 — 월 「202609」, 분기 「202603」(2026년 3분기)."""
    out: list[str] = []
    y, m = today.year, today.month
    if cycle == "QY":
        q = (m - 1) // 3 + 1
        for _ in range(n):
            out.append(f"{y}{q:02d}")
            y, q = (y, q - 1) if q > 1 else (y - 1, 4)
    else:
        for _ in range(n):
            out.append(f"{y}{m:02d}")
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out


def pick(rows: list[dict[str, Any]], item_word: str, region_col: str) -> list[dict[str, Any]]:
    """받은 줄 → 저장할 줄 (순수 함수). 항목 이름이 맞는 것만, 오피스텔은 면적 「전체」만, 지역마다 한 줄."""
    whole = any(r.get("CLS_NM") == "전체" for r in rows) and region_col == "GRP_NM"
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        region, val = str(r.get(region_col) or "").strip(), r.get("DTA_VAL")
        if not region or val is None or item_word not in str(r.get("ITM_NM") or ""):
            continue
        if whole and r.get("CLS_NM") != "전체":
            continue
        out.setdefault(region, {"region": region, "period": str(r.get("WRTTIME_DESC") or ""),
                                "value": float(val), "unit": r.get("UI_NM")})  # fmt: skip
    return list(out.values())


def fetch(
    client: httpx.Client, key: str, table: str, cycle: str, period: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        time.sleep(GAP)
        d = client.get(URL, params={"KEY": key, "Type": "json", "pIndex": page, "pSize": 1000, "STATBL_ID": table,
                                    "DTACYCLE_CD": cycle, "WRTTIME_IDTFR_ID": period}).json()  # fmt: skip
        body = d.get("SttsApiTblData")
        if not body:
            return rows  # 그 시점 자료 없음(RESULT 만 옴)
        part = next((x["row"] for x in body if "row" in x), [])
        total = next((h.get("list_total_count") for x in body if "head" in x for h in x["head"]
                      if "list_total_count" in h), 0)  # fmt: skip
        rows += part
        if not part or len(rows) >= int(total or 0):
            return rows
        page += 1


def dry(key: str) -> None:
    """DB 에 안 넣고 받아만 봄 — 통계마다 시점 · 지역 수 · 수도권 지역 이름을 logs/rone_dry.log 에."""
    from aucs_workers.db import ROOT

    out = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for name, (table, cycle, word, col) in TABLES.items():
            got: list[dict[str, Any]] = []
            raw: list[dict[str, Any]] = []
            for p in periods(cycle, date.today()):
                raw = fetch(client, key, table, cycle, p)
                got = pick(raw, word, col)
                if got or raw:
                    break
            items = sorted({str(r.get("ITM_NM")) for r in raw})
            out.append(
                f"[{name}] 받은 줄 {len(raw)} · 고른 줄 {len(got)} · 시점 {got[0]['period'] if got else '-'} · 항목 {items[:8]}"
            )
            near = [
                f"{g['region']}={g['value']:.2f}"
                for g in got
                if g["region"].split(">")[0] in ("서울", "경기", "인천", "수도권")
            ]
            out.append("   수도권: " + " | ".join(near[:70]))
    (ROOT / "logs" / "rone_dry.log").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("끝: logs/rone_dry.log")


def main() -> None:
    key = os.getenv("RONE_API_KEY", "").strip().strip("\"'")
    if not key:
        raise SystemExit("RONE_API_KEY 가 비어 있습니다 (.env)")
    if "--dry" in sys.argv:
        return dry(key)
    today = date.today()
    with connect() as conn, run(conn, "rone", "R-ONE 지역 평균") as job:
        if not conn.execute("select to_regclass('ref.region_stats')").fetchone()[0]:
            raise SystemExit("ref.region_stats 표가 없습니다 — 이주 0060 을 먼저 적용하세요.")
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            for name, (table, cycle, word, col) in TABLES.items():
                got: list[dict[str, Any]] = []
                for p in periods(cycle, today):
                    got = pick(fetch(client, key, table, cycle, p), word, col)
                    if got:
                        break
                if not got:
                    print(f"  {name}: 최근 시점 자료를 못 찾음 — 예전 값 그대로 둠")
                    continue
                conn.execute("delete from ref.region_stats where stat_key = %s", (name,))
                with conn.cursor() as cur:
                    cur.executemany(
                        "insert into ref.region_stats (stat_key, region, period, value, unit)"
                        " values (%(k)s, %(region)s, %(period)s, %(value)s, %(unit)s)",
                        [{**g, "k": name} for g in got],
                    )
                conn.commit()
                job.count += len(got)
                print(f"  {name}: {got[0]['period']} · 지역 {len(got):,}곳")
    print(f"끝: {job.count:,}줄")


if __name__ == "__main__":
    main()
