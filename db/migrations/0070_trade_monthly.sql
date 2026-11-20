-- 실거래 지난 자료 요약(11/20 · 11/21 대표님): 원본(2006~, 수천만 줄)은 대표님 PC 파일(D:\Auction\data\실거래),
-- DB 에는 단지(지번) · 면적 · 달마다 건수 · 최저 · 평균 · 최고만. 채우는 코드: workers jobs/trade_summary.py
-- 매매만 · 해제 거래 빼고 · 수도권(ref.regions 에 있는 법정동)만 — 전국은 ref.regions 를 넓힐 때.
-- 화면(실거래 전체 보기 · 실거래 vs 낙찰가)은 이 표만 읽음. 최근 2년 원본은 그대로 core.trades.
create table if not exists core.trade_monthly (
  prop_type text not null,            -- apt · rowhouse · house · officetel · commercial
  region_code text not null,          -- 법정동 10자리(core.trades 와 같은 셈)
  lot_no text not null,               -- 지번(없으면 '')
  area_m2 integer not null,           -- 전용(건물)면적을 ㎡ 반올림(상가는 큰 건물이 있어 integer)
  ym date not null,                   -- 계약 달 1일
  complex_name text,
  build_year smallint,
  n integer not null,
  min_krw bigint not null,
  avg_krw bigint not null,
  max_krw bigint not null,
  primary key (prop_type, region_code, lot_no, area_m2, ym)
);
create index if not exists trade_monthly_lot on core.trade_monthly (region_code, lot_no);
alter table core.trade_monthly enable row level security;
