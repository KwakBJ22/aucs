"""우리 낙찰 자료를 읽기 전용으로 내려받아 표(parquet)로 저장한다.

- core.sale_results (2026-09-30~) + analysis.sale_snapshots 의 입찰 전 분석(층 · 신호 · 임차인 수).
- 읽기만 한다: 트랜잭션을 read only 로 열고 SELECT 만 보낸다. 쓰기 · 이주 없음.
- 연결 주소는 저장소 .env 의 DATABASE_URL 을 읽기만 한다(값은 출력하지 않음).
- 분석 스냅샷은 매각일 「전」에 찍힌 것만 쓴다(analysis_at 날짜 < sale_date).

실행: uv run ... python tools/predict_lab/export_ours.py
"""

import re
from pathlib import Path

from paths import OURS_PARQUET, SRC_DIR

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

SQL = """
select s.court_code, s.case_no, s.item_no, s.sale_date, s.usage_name, s.region_code,
       s.address, s.building_area_m2, s.appraisal_krw, s.min_price_krw, s.winning_bid_krw,
       s.failed_count, s.result, s.is_share, s.is_special_case,
       a.tenant_count, a.signal_count, a.high_count
from core.sale_results s
left join lateral (
  select (x.analysis->>'tenant_count')::int as tenant_count,
         jsonb_array_length(x.analysis->'signals') as signal_count,
         (select count(*) from jsonb_array_elements(x.analysis->'signals') e
           where e->>'level' = 'high') as high_count
  from analysis.sale_snapshots x
  where x.court_code = s.court_code and x.case_no = s.case_no and x.item_no = s.item_no
    and x.sale_date = s.sale_date and x.analysis_at::date < s.sale_date
    and jsonb_typeof(x.analysis->'signals') = 'array'
  order by x.analysis_at desc limit 1
) a on true
where s.sale_date >= '2026-07-01'
order by s.sale_date, s.court_code, s.case_no, s.item_no
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
    df = pd.DataFrame(rows, columns=cols)
    df.to_parquet(OURS_PARQUET, index=False)
    return len(df)


if __name__ == "__main__":
    n = export()
    print(f"우리 낙찰 자료 {n}건 → {OURS_PARQUET}")
