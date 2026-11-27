-- 예정물건(11/27 대표님 — 탱크옥션 「예정물건」처럼 매각공고 전 사건을 먼저 보여 주기).
-- 출처: 법원경매정보 「배당요구종기공고」(경매개시결정 뒤 법원이 올리는 공고 — 사건번호 · 개시결정일 · 배당요구종기 · 소재지).
-- 매각공고(물건 목록)는 배당요구종기 뒤 몇 달 지나 나오므로, 그 사이 사건을 여기에 둠. 물건 목록에 들어오면(core.cases) 예정에서 빠짐.
-- 이름(소유자 · 채무자 · 채권자)은 원본(raw)에만 — 여기에는 두지 않음.

insert into ref.sources (source_id, name_ko, display_policy, redistributable, retention_note) values
  ('court_notices', '법원 배당요구종기공고', 'public', true, '매각공고 전 사건 — 날마다 한 번')
on conflict (source_id) do nothing;

create table if not exists raw.court_notice_raw (
  raw_id       bigint generated always as identity primary key,
  source_id    text not null default 'court_notices' references ref.sources(source_id),
  court_code   text not null,
  doc_key      text not null,           -- 사건번호(내부, csNo)
  sale_date    date,                    -- 쓰지 않음(raw 표 모양을 맞춤)
  payload      jsonb not null,
  checksum     text not null,
  fetched_at   timestamptz not null default now()
);
create unique index if not exists court_notice_raw_key on raw.court_notice_raw (court_code, doc_key, checksum);
alter table raw.court_notice_raw enable row level security;

create table if not exists core.upcoming_cases (
  court_code        text not null,
  case_no           text not null,          -- 「2026타경101761」
  dept_code         text,                   -- 담당계 코드(1001 = 경매1계)
  ordered_date      date,                   -- 경매개시결정일
  claim_deadline    date,                   -- 배당요구종기
  notice_date       date,                   -- 배당요구종기 공고일
  sido              text,
  sigungu           text,
  dong              text,                   -- 읍 · 면 · 동(리까지)
  lot_no            text,                   -- 대표 지번
  road_address      text,
  building_name     text,
  building_detail   text,                   -- 「 8층809호」
  item_count        int,                    -- 매각 목적물 수(법원이 적은 때만)
  first_seen_at     timestamptz not null default now(),
  last_seen_at      timestamptz not null default now(),
  primary key (court_code, case_no)
);
create index if not exists upcoming_cases_region on core.upcoming_cases (sido, sigungu, dong);
create index if not exists upcoming_cases_seen on core.upcoming_cases (last_seen_at desc);
comment on table core.upcoming_cases is '예정물건 — 배당요구종기공고에 오른 사건(매각공고 전). 11/27';
alter table core.upcoming_cases enable row level security;
