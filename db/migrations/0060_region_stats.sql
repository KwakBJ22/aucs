-- 0060 (11/15): 지역 평균 통계(한국부동산원 R-ONE) — 상가 수익률 · 공실률, 오피스텔 수익률, 전월세전환율.
-- collectors/rone.py 가 가장 최근 시점만 받아 통계마다 통째로 갈아 끼움. 분석이 물건의 지역 · 용도에 맞는 줄을 골라
-- 결과(area_stats)에 붙임 → 상세 「무엇을 사나」의 「이 지역 평균」 한 줄.

create table if not exists ref.region_stats (
  stat_key text not null,            -- shop_yield · shop_vacancy · officetel_yield · officetel_conv · conv_apt · conv_row · conv_house
  region text not null,              -- R-ONE 지역 이름(「경기>수원시」 · 「서울」)
  period text not null,              -- 「2026년 3분기」 · 「2026년 9월」
  value numeric not null,
  unit text,
  fetched_at timestamptz not null default now(),
  primary key (stat_key, region)
);
comment on table ref.region_stats is '지역 평균 통계(한국부동산원 R-ONE, 가장 최근 시점만) — 분석이 읽음';
revoke all on ref.region_stats from anon, authenticated;
