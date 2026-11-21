-- 낙찰 순간 기록(11/21 대표님 「핵심 경쟁력 — 매우 중요하게」): 매각기일 결과(낙찰 · 유찰)마다
-- 입찰일 전에 우리가 보여 준 분석(시세 · 예상 낙찰가율 · 신호 · 건물)을 그대로 얼려 둠.
-- 분석은 나중에 다시 돌면 바뀌므로, 요인별 「낙찰가 ÷ 시세」를 재려면 그때 값이 따로 있어야 함(claude/요인표.md).
-- 채우는 코드: workers jobs/sale_snapshot.py(아침 묶음 「매각결과」 바로 뒤). 한 번 넣은 줄은 바꾸지 않음.
create table if not exists analysis.sale_snapshots (
  item_id text not null,
  sale_date date not null,
  result text not null,                 -- sold · failed (core.sale_results.result)
  court_code text,
  case_no text,
  item_no integer,
  usage_name text,
  building_area_m2 numeric,
  appraisal_krw bigint,
  min_price_krw bigint,
  winning_bid_krw bigint,
  sale_rate numeric,                    -- 낙찰가 ÷ 감정가 %
  failed_count integer,
  is_share boolean,
  is_special_case boolean,
  analysis_version integer not null,    -- 입찰일 0시(한국) 전에 만든 마지막 분석
  analysis_at timestamptz not null,
  engine_version text,
  analysis jsonb not null,              -- 그 분석 결과 통째로(analysis.item_analysis.result)
  snapped_at timestamptz not null default now(),
  primary key (item_id, sale_date)
);
create index if not exists sale_snapshots_date on analysis.sale_snapshots (sale_date);
alter table analysis.sale_snapshots enable row level security;
