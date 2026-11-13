-- 0047 주소 → 좌표(11/13 대표님 「입지」) — 정비사업 구역 대표지번을 한 번만 좌표로 바꿔 둠(브이월드 주소 좌표 검색).
-- 물건 상세 「가까운 정비사업」이 물건에서 구역까지 직선거리를 셈. 공개 자료라 API(관리자 연결)만 읽음.
create table if not exists ref.place_points (
  address    text primary key,                 -- 「서울특별시 관악구 봉천동 1544-1」
  geom       geography(Point, 4326),           -- 못 찾았으면 비어 있음
  result     text not null default 'ok',       -- ok / none
  fetched_at timestamptz not null default now()
);
comment on table ref.place_points is '주소 → 좌표(브이월드). redev_geo 수집기가 정비사업 대표지번을 넣음(11/13).';
create index if not exists place_points_geom on ref.place_points using gist (geom);
alter table ref.place_points enable row level security;
