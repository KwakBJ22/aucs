-- 공시가격(11/11 대표님 — 재산세·종부세 셈 준비): 브이월드 국가중점데이터 API 응답을 그대로 둠.
-- kind: apt(공동주택가격) · house(개별주택가격) · land(개별공시지가). 화면·계산은 분석이 이 원문을 읽어 씀.
create table if not exists raw.official_price_raw (
  item_id text not null,
  kind text not null check (kind in ('apt', 'house', 'land')),
  pnu text not null,
  std_year int,
  payload jsonb not null,
  fetched_at timestamptz not null default now(),
  primary key (item_id, kind)
);
comment on table raw.official_price_raw is '공시가격 원문(브이월드 getApartHousingPriceAttr·getIndvdHousingPriceAttr·getIndvdLandPriceAttr). official_prices 수집기가 넣음(11/11).';
create index if not exists official_price_raw_pnu on raw.official_price_raw (pnu, kind);
alter table raw.official_price_raw enable row level security;
