-- 0024 공매(온비드) — 경매와 표를 따로 둠(저감·회차 구조와 낙찰가율 분모가 다름). 설계: 「옥스 공매 화면설계서」 2절.
-- MCP로 적용(10/28).
-- 공개 자료라 RLS 켜고 API(관리자 연결)만 읽음(0019 와 같음).

-- 받은 그대로(칸 이름이 예상과 달라도 다시 받지 않고 정리 SQL만 고치게)
create table if not exists raw.onbid_raw (
  kind       text not null check (kind in ('item', 'notice', 'result')),
  key        text not null,                -- item: 물건관리번호|공매조건번호 · notice: 공고번호 · result: 물건관리번호|개찰일시|공고번호
  payload    jsonb not null,
  fetched_at timestamptz not null default now(),
  primary key (kind, key)
);

-- 공고(공고일이 「새 물건」 기준 — 압류재산은 2주에 한 번 몰아 개찰해서 개찰일로 보면 빠짐)
create table if not exists core.onbid_notices (
  notice_no   text primary key,
  notice_date date,
  name        text,
  org_name    text,
  kind_name   text,
  fetched_at  timestamptz not null default now()
);

-- 진행·예정 물건(물건관리번호 하나에 한 줄 = 지금 회차)
create table if not exists core.onbid_items (
  item_id        text primary key,           -- 'OB-' || 물건관리번호 → 화면 주소 /item/[id] 그대로
  mng_no         text not null unique,
  kind           text not null,              -- seized(압류) · public(국유·수탁) · general(기타일반) · trust(신탁) · finance(금융기관)
  kind_name      text,
  disposal       text,                       -- 매각 · 임대 …(화면은 매각만)
  title          text,
  address        text,
  sido           text,
  sigungu        text,
  dong           text,
  region_code    text,
  lot_no         text,
  usage_name     text,
  land_m2        numeric,
  building_m2    numeric,
  appraisal_krw  bigint,
  min_price_krw  bigint,
  failed_count   int,
  bid_start      timestamptz,                -- 일정 미정(2999·9999년)은 비움
  bid_end        timestamptz,
  open_at        timestamptz,
  status_name    text,                       -- 입찰준비중 · 입찰진행중 …
  notice_no      text,
  status_code    text not null default 'active' check (status_code in ('active', 'gone')),
  display_policy text not null default 'public',
  fetched_at     timestamptz not null default now(),
  checked_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index if not exists onbid_items_bid_end_idx on core.onbid_items (bid_end);
create index if not exists onbid_items_region_idx on core.onbid_items (region_code);

-- 회차(온비드가 앞으로 회차까지 미리 줌 → 다음 회차 최저가를 계산하지 않고 그대로 씀)
create table if not exists core.onbid_rounds (
  item_id       text not null references core.onbid_items (item_id) on delete cascade,
  cond_no       text not null,               -- 공매조건번호(회차마다 다름)
  bid_start     timestamptz,
  bid_end       timestamptz,
  open_at       timestamptz,
  min_price_krw bigint,
  status_name   text,
  checked_at    timestamptz not null default now(),
  primary key (item_id, cond_no)
);

-- 입찰 결과(개찰 끝난 회차) — 통계용, 전국. 낙찰가율은 최저가 대비(공매) · 감정가 대비 둘 다
create table if not exists core.onbid_results (
  mng_no          text not null,
  opened_at       timestamptz not null,
  notice_no       text not null default '',
  item_seq        text,
  kind_name       text,
  disposal        text,
  usage_l         text,
  usage_m         text,
  usage_s         text,
  title           text,                      -- 압류재산은 주소가 가려져 옴(*****)
  sido            text,
  land_m2         numeric,
  building_m2     numeric,
  appraisal_krw   bigint,
  min_price_krw   bigint,
  win_krw         bigint,
  failed_round    numeric,
  bidders         int,
  invalid_bidders int,
  rate_appraisal  numeric,
  rate_min        numeric,                   -- 최저가 대비 낙찰가율(%) — 100을 넘는 게 보통
  result          text,                      -- 낙찰 · 유찰 · 취소 · 수의계약가능
  source          text not null,             -- api · 낙찰가DB_20261012
  loaded_at       timestamptz not null default now(),
  primary key (mng_no, opened_at, notice_no)
);
create index if not exists onbid_results_sold_idx on core.onbid_results (result, sido, opened_at);

alter table raw.onbid_raw enable row level security;
alter table core.onbid_notices enable row level security;
alter table core.onbid_items enable row level security;
alter table core.onbid_rounds enable row level security;
alter table core.onbid_results enable row level security;

comment on table core.onbid_items is '온비드 진행·예정 물건(서울·경기) · 경매와 섞지 않음 · item_id = OB-물건관리번호';
comment on table core.onbid_results is '온비드 입찰결과(전국, 통계용) · rate_min = 최저가 대비 낙찰가율';
