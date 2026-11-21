-- 실거래 지난 자료 요약을 해마다로(11/21 대표님 「작업해」): 튀는 거래는 시세와 같은 규칙으로 빼고 중간값.
-- 규칙: aucs_rules.price._drop_outliers(㎡당 가격 사분위 범위 1.5배 밖 제외, 4건 미만이면 그대로) — 시세 계산과 같은 코드.
-- 채우는 코드: workers jobs/trade_summary.py · 읽는 곳: API services/item_trades.py(실거래 전체 보기).
-- core.trade_monthly(0070)는 이제 안 씀 — 지우는 것은 대표님 허락 뒤 따로.
create table if not exists core.trade_yearly (
  prop_type text not null,            -- apt · rowhouse · house · officetel · commercial
  region_code text not null,          -- 법정동 10자리(core.trades 와 같은 셈)
  lot_no text not null,               -- 지번(없으면 '')
  area_m2 integer not null,           -- 전용(건물)면적 ㎡ 반올림
  y smallint not null,                -- 계약 연도
  names text,                         -- 단지 이름(한 지번에 여럿이면 「 · 」로)
  build_year smallint,
  last_month date,                    -- 그해 마지막 계약 달 1일
  n_all integer not null,             -- 신고된 거래 수(해제 빼고)
  n integer not null,                 -- 튀는 거래 뺀 뒤
  mid_krw bigint not null,            -- 중간값
  low_krw bigint not null,            -- 뺀 뒤 최저
  high_krw bigint not null,           -- 뺀 뒤 최고
  primary key (prop_type, region_code, lot_no, area_m2, y)
);
create index if not exists trade_yearly_lot on core.trade_yearly (region_code, lot_no);
alter table core.trade_yearly enable row level security;
