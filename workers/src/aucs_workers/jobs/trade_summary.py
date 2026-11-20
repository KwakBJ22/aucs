"""실거래 지난 자료(PC 파일) → core.trade_monthly 요약(11/21 대표님 「작업해」).

    uv run python -m aucs_workers.jobs.trade_summary                     # 받아 둔 종류 모두
    uv run python -m aucs_workers.jobs.trade_summary --types apt_sale    # 한 종류만

- 원본: trades_archive 가 받은 D:\\Auction\\data\\실거래\\{종류}\\{연도}\\{시군구}.jsonl.gz
- 한 줄 고르기는 매월 수집(trades.parse_trade)과 같은 셈 — 해제 거래 · 날짜 없는 줄 빼고, 법정동은 ref.regions 로.
- 수도권(ref.regions 에 있는 시군구)만. 토지는 지번이 가려져 와서 뺌.
- 종류마다 통째로 바꿔 넣음(지우고 넣기를 한 묶음으로) — 몇 번 돌려도 같음. 이어 받기가 끝날 때마다 다시 돌리면 됨.
"""

import argparse
import gzip
import json
import time
from collections import defaultdict
from datetime import date

from aucs_workers.collectors.trades import TYPES, parse_trade
from aucs_workers.collectors.trades_archive import ROOT
from aucs_workers.db import connect

COLS = ["prop_type", "region_code", "lot_no", "area_m2", "ym", "complex_name", "build_year",
        "n", "min_krw", "avg_krw", "max_krw"]  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    names = [
        p.name
        for p in sorted(ROOT.iterdir())
        if p.is_dir() and p.name in TYPES and p.name != "land_sale"
    ]
    ap.add_argument("--types", nargs="*", default=names)
    a = ap.parse_args()
    with connect() as conn:
        rows = conn.execute(
            "select region_code, sigungu_code, eupmyeondong from ref.regions where level = 'dong'"
        ).fetchall()
        region = {(s, e): rc for rc, s, e in rows}
        sggs = {s for _, s, _ in rows}
        for name in a.types:
            prop = TYPES[name][3]
            t0, read, skip = time.monotonic(), 0, 0
            # (지역, 지번, 면적, 달) → [건수, 최저, 합, 최고, 단지 이름, 준공 연도]
            acc: dict[tuple[str, str, int, date], list] = defaultdict(
                lambda: [0, None, 0, None, None, None]
            )
            for f in sorted(ROOT.glob(f"{name}/*/*.jsonl.gz")):
                sgg = f.name[:5]
                if sgg not in sggs:
                    continue
                with gzip.open(f, "rt", encoding="utf-8") as g:
                    for line in g:
                        read += 1
                        r = parse_trade(json.loads(line), "sale", prop, sgg, region)
                        if not r or not r["price_krw"] or not r["region_code"]:
                            skip += 1
                            continue
                        d = r["deal_date"]
                        k = (
                            r["region_code"],
                            r["lot_no"] or "",
                            round(r["area_m2"] or 0),
                            date(d.year, d.month, 1),
                        )
                        s, p = acc[k], r["price_krw"]
                        s[0] += 1
                        s[1] = p if s[1] is None else min(s[1], p)
                        s[2] += p
                        s[3] = p if s[3] is None else max(s[3], p)
                        s[4] = r["complex_name"] or s[4]
                        s[5] = r["build_year"] or s[5]
            with conn.transaction():
                conn.execute("delete from core.trade_monthly where prop_type = %s", (prop,))
                with (
                    conn.cursor() as cur,
                    cur.copy(f"copy core.trade_monthly ({', '.join(COLS)}) from stdin") as cp,
                ):
                    for (rc, lot, area, ym), (n, lo, tot, hi, nm, by) in acc.items():
                        cp.write_row([prop, rc, lot, area, ym, nm, by, n, lo, round(tot / n), hi])
            conn.commit()  # 종류마다 바로 남김
            print(f"{name}: 원본 {read:,}줄 · 뺀 줄 {skip:,} · 요약 {len(acc):,}줄 · "
                  f"{(time.monotonic() - t0) / 60:.1f}분", flush=True)  # fmt: skip


if __name__ == "__main__":
    main()
