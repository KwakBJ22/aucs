"""실거래 지난 자료(PC 파일) → core.trade_yearly 요약(11/21 대표님 「작업해」).

    uv run python -m aucs_workers.jobs.trade_summary                     # 받아 둔 종류 모두
    uv run python -m aucs_workers.jobs.trade_summary --types apt_sale    # 한 종류만

- 원본: trades_archive 가 받은 D:\\Auction\\data\\실거래\\{종류}\\{연도}\\{시군구}.jsonl.gz
- 한 줄 고르기는 매월 수집(trades.parse_trade)과 같은 셈 — 해제 거래 · 날짜 없는 줄 빼고, 법정동은 ref.regions 로.
- 단지(지번) · 면적(㎡ 반올림) · 연도마다: 튀는 거래는 시세 계산과 같은 규칙(aucs_rules.price._drop_outliers,
  ㎡당 가격 사분위 범위 1.5배 밖)으로 빼고 중간값 · 최저 · 최고. 신고된 건수(n_all)도 남김.
  (11/21 대표님: 보여 주는 건 다 보여 주되, 값을 셀 때는 튀는 거래를 빼서 믿을 수 있게)
- 수도권(ref.regions 에 있는 시군구)만. 토지는 지번이 가려져 와서 뺌.
- 파일 하나가 (연도, 시군구) 하나라 파일마다 묶어 씀. 종류마다 지우고 넣기를 한 묶음으로 — 몇 번 돌려도 같음.
"""

import argparse
import gzip
import json
import time
from datetime import date
from statistics import median

from aucs_rules.price import Trade, _drop_outliers

from aucs_workers.collectors.trades import TYPES, parse_trade
from aucs_workers.collectors.trades_archive import ROOT
from aucs_workers.db import connect

COLS = ["prop_type", "region_code", "lot_no", "area_m2", "y", "names", "build_year", "last_month",
        "n_all", "n", "mid_krw", "low_krw", "high_krw"]  # fmt: skip


def summarize(prop: str, key: tuple[str, str, int, int], got: list[dict]) -> list:
    """한 (지역, 지번, 면적, 연도)의 거래들 → 요약 한 줄(순수 함수)."""
    rc, lot, area, y = key
    trades = [Trade(r["deal_date"], r["price_krw"], r["area_m2"], r["floor"], None) for r in got]
    kept = _drop_outliers(trades) or trades
    prices = sorted(t.price_krw for t in kept)
    names = " · ".join(sorted({r["complex_name"] for r in got if r["complex_name"]})) or None
    built = max((r["build_year"] for r in got if r["build_year"]), default=None)
    last = max(r["deal_date"] for r in got)
    return [prop, rc, lot, area, y, names, built, date(last.year, last.month, 1),
            len(got), len(kept), int(median(prices)), prices[0], prices[-1]]  # fmt: skip


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
            t0, read, skip, n_rows, dropped = time.monotonic(), 0, 0, 0, 0
            with conn.transaction():
                # 파일 수천 개를 읽는 동안 COPY 하나가 열려 있음 — DB 기본 시간 제한(11/21 apt 23만 줄째에서 걸림)을 이 묶음에서만 풂
                conn.execute("set local statement_timeout = 0")
                conn.execute("delete from core.trade_yearly where prop_type = %s", (prop,))
                with (
                    conn.cursor() as cur,
                    cur.copy(f"copy core.trade_yearly ({', '.join(COLS)}) from stdin") as cp,
                ):
                    for f in sorted(ROOT.glob(f"{name}/*/*.jsonl.gz")):
                        sgg = f.name[:5]
                        if sgg not in sggs:
                            continue
                        groups: dict[tuple[str, str, int, int], list[dict]] = {}
                        with gzip.open(f, "rt", encoding="utf-8") as g:
                            for line in g:
                                read += 1
                                r = parse_trade(json.loads(line), "sale", prop, sgg, region)
                                if not r or not r["price_krw"] or not r["region_code"] or not r["area_m2"]:  # fmt: skip
                                    skip += 1
                                    continue
                                k = (r["region_code"], r["lot_no"] or "", round(r["area_m2"]), r["deal_date"].year)  # fmt: skip
                                groups.setdefault(k, []).append(r)
                        for k, got in groups.items():
                            row = summarize(prop, k, got)
                            dropped += row[8] - row[9]
                            cp.write_row(row)
                            n_rows += 1
            conn.commit()  # 종류마다 바로 남김
            print(f"{name}: 원본 {read:,}줄 · 뺀 줄 {skip:,} · 튀는 거래 {dropped:,} · 요약 {n_rows:,}줄 · "
                  f"{(time.monotonic() - t0) / 60:.1f}분", flush=True)  # fmt: skip


if __name__ == "__main__":
    main()
