-- 0063 (11/16): 상가 물건 주변 가게(소상공인시장진흥공단 상가(상권)정보, 공공데이터포털 15012005).
-- collectors/stores.py 가 상가 · 근린시설 물건마다 반경 300m 가게를 받아 업종별로 세어 한 줄로 둠(가게 줄은 안 둠).
-- 같은 필지(필지번호 lnoCd = 물건 PNU)에 든 가게는 층 · 업종만 따로 — 「이 건물에 든 가게」.

create table if not exists core.item_stores (
  item_id text primary key,
  radius_m int not null,
  total int not null,                -- 반경 안 가게 수
  by_large jsonb not null default '{}', -- 업종 대분류별 수 {"음식": 412, "소매": 230, …}
  by_mid jsonb not null default '{}',   -- 업종 중분류별 수(많은 순 상위 15)
  same_parcel int not null default 0,   -- 같은 필지 가게 수
  same_list jsonb not null default '[]',-- 같은 필지 가게 [{"floor": "1", "ho": "104", "large": "음식", "small": "카페"}]
  fetched_at timestamptz not null default now()
);
comment on table core.item_stores is '상가 물건 반경 300m 가게 업종 분포(소상공인 상권정보) — 분석이 읽음';
revoke all on core.item_stores from anon, authenticated;
