-- 0019 건축물대장(건축HUB 표제부·층별개요) — 경매 물건 지번만 받아 둠. 공개 자료라 RLS 없이 API(관리자 연결)만 읽음.
-- MCP로 적용(10/27).
create table if not exists core.building_register (
  region_code text not null,          -- 법정동코드 10자리
  lot_no      text not null,          -- 번-지 (예 0508-0123, 산은 앞에 산)
  kind        text not null check (kind in ('title', 'floor')),
  seq         int  not null,
  data        jsonb not null,
  fetched_at  timestamptz not null default now(),
  primary key (region_code, lot_no, kind, seq)
);
create table if not exists core.building_fetch (
  region_code text not null,
  lot_no      text not null,
  last_at     timestamptz not null default now(),
  result      text not null,          -- ok / none / partial / bad_lot
  titles      int not null default 0,
  floors      int not null default 0,
  primary key (region_code, lot_no)
);
alter table core.building_register enable row level security;
alter table core.building_fetch enable row level security;
