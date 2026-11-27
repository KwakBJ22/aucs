"""우리 낙찰 자료를 읽기 전용으로 내려받아 표(parquet)로 저장한다.

- core.sale_results (2026-09-30~) + analysis.sale_snapshots 의 입찰 전 분석(층 · 신호 · 임차인 수).
- 읽기만 한다: 트랜잭션을 read only 로 열고 SELECT 만 보낸다. 쓰기 · 이주 없음.
- 연결 주소는 저장소 .env 의 DATABASE_URL 을 읽기만 한다(값은 출력하지 않음).
- 분석 스냅샷은 매각일 「전」에 찍힌 것만 쓴다(analysis_at 날짜 < sale_date).

실행: uv run ... python tools/predict_lab/export_ours.py
"""

import json
import re
from pathlib import Path

from paths import ITEMS_PARQUET, OURS_PARQUET, REDUCTION_JSON, SRC_DIR

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

SQL = """
select s.court_code, s.case_no, s.item_no, s.sale_date, s.usage_name, s.sido as sido_name, it.sigungu as sigungu_txt, s.region_code,
       s.address, coalesce(s.building_area_m2, it.building_area_m2) as building_area_m2, s.appraisal_krw, s.min_price_krw, s.winning_bid_krw,
       s.failed_count, s.price_round, s.result, s.is_share, s.is_special_case,
       a.tenant_count, a.signal_count, a.high_count,
       a.snap_p25, a.snap_p50, a.snap_p75, a.snap_n, a.snap_scope, a.snap_date, a.snap_engine
from core.sale_results s
left join core.items it on it.item_id = s.item_id
left join lateral (
  select (x.analysis->>'tenant_count')::int as tenant_count,
         jsonb_array_length(x.analysis->'signals') as signal_count,
         (select count(*) from jsonb_array_elements(x.analysis->'signals') e
           where e->>'level' = 'high') as high_count,
         (x.analysis->'sale_rate'->>'p25')::float8 as snap_p25,
         (x.analysis->'sale_rate'->>'p50')::float8 as snap_p50,
         (x.analysis->'sale_rate'->>'p75')::float8 as snap_p75,
         (x.analysis->'sale_rate'->>'n')::int as snap_n,
         x.analysis->'sale_rate'->>'scope' as snap_scope,
         x.analysis_at::date as snap_date,
         x.engine_version as snap_engine
  from analysis.sale_snapshots x
  where x.court_code = s.court_code and x.case_no = s.case_no and x.item_no = s.item_no
    and x.sale_date = s.sale_date and x.analysis_at::date < s.sale_date
    and jsonb_typeof(x.analysis->'signals') = 'array'
  order by x.analysis_at desc limit 1
) a on true
where s.sale_date >= '2026-07-01'
order by s.sale_date, s.court_code, s.case_no, s.item_no
"""


ITEMS_SQL = """
select split_part(case_id, '-', 1) as court_code,
       substr(case_id, position('-' in case_id) + 1) as case_no,
       item_no, address, lot_no, region_code
from core.items
"""
REDUCTION_SQL = """
select value from ref.rule_tables where rule_key = 'court_reduction_pct'
order by valid_from desc limit 1
"""


def _database_url() -> str:
    text = ENV_FILE.read_text(encoding="utf-8")
    m = re.search(r"^DATABASE_URL=(.+)$", text, re.M)
    if not m:
        raise SystemExit("DATABASE_URL 이 .env 에 없습니다")
    return m.group(1).strip().strip('"').strip("'")


def export() -> int:
    import pandas as pd
    import psycopg

    SRC_DIR.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(_database_url()) as conn:
        conn.read_only = True  # 쓰기 금지 (세션 단위)
        with conn.cursor() as cur:
            cur.execute(SQL)
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
            cur.execute(ITEMS_SQL)
            icols = [d.name for d in cur.description]
            items = cur.fetchall()
            cur.execute(REDUCTION_SQL)
            red = cur.fetchone()
    df = pd.DataFrame(rows, columns=cols)
    df.to_parquet(OURS_PARQUET, index=False)
    pd.DataFrame(items, columns=icols).to_parquet(ITEMS_PARQUET, index=False)
    table = dict(red[0]) if red else {}
    REDUCTION_JSON.write_text(
        json.dumps(
            {
                "pct": {
                    c: v["pct"]
                    for c, v in table.items()
                    if isinstance(v, dict) and v.get("pct") is not None
                },
                "verified": sorted(
                    c for c, v in table.items() if isinstance(v, dict) and v.get("verified")
                ),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"물건 주소 {len(items)}건 · 법원 저감률 {len(table)}곳")
    return len(df)


if __name__ == "__main__":
    n = export()
    print(f"우리 낙찰 자료 {n}건 → {OURS_PARQUET}")
