-- 0002 본 표: 원본(raw)·기준(ref)·정리(core)·계산(analysis)
-- 이름 규칙: docs/glossary.md. 금액 _krw(bigint), 날짜 _date, 시각 _at(timestamptz).

-- ───────── raw: 받은 그대로, 추가만 ─────────
create table raw.court_item_raw (
  raw_id       bigint generated always as identity primary key,
  source_id    text not null default 'court_items' references ref.sources(source_id),
  court_code   text not null,
  doc_key      text not null,           -- 법원 docid
  sale_date    date,                    -- 매각기일(maeGiil)
  payload      jsonb not null,          -- 법원이 보낸 모든 칸
  checksum     text not null,
  fetched_at   timestamptz not null default now()
);
create index on raw.court_item_raw (doc_key, sale_date, fetched_at desc);
create unique index on raw.court_item_raw (doc_key, sale_date, checksum);

create table raw.court_result_raw (
  raw_id       bigint generated always as identity primary key,
  source_id    text not null default 'court_results' references ref.sources(source_id),
  court_code   text not null,
  doc_key      text not null,
  sale_date    date,
  payload      jsonb not null,
  checksum     text not null,
  fetched_at   timestamptz not null default now()
);
create unique index on raw.court_result_raw (doc_key, sale_date, checksum);

create table raw.court_doc_raw (
  raw_id       bigint generated always as identity primary key,
  source_id    text not null default 'court_docs' references ref.sources(source_id),
  case_id      text not null,
  doc_kind     text not null,           -- case_info, schedule, deliveries, status_report, spec_sheet, item_detail …
  payload      jsonb,
  file_path    text,                    -- 저장소(파일) 주소
  checksum     text not null,
  fetched_at   timestamptz not null default now()
);
create unique index on raw.court_doc_raw (case_id, doc_kind, checksum);

create table raw.trade_raw (
  raw_id       bigint generated always as identity primary key,
  source_id    text not null default 'trades' references ref.sources(source_id),
  prop_type    text not null,
  deal_kind    text not null,           -- sale / lease
  lawd_cd      text not null,           -- 시군구코드 5자리
  deal_ym      text not null,           -- YYYYMM
  payload      jsonb not null,
  checksum     text not null,
  fetched_at   timestamptz not null default now()
);
create unique index on raw.trade_raw (prop_type, deal_kind, lawd_cd, deal_ym, checksum);

-- ───────── ref: 기준표 ─────────
create table ref.courts (
  court_code   text primary key,
  name_ko      text not null,
  sido         text not null
);
insert into ref.courts values
  ('B000210','서울중앙','서울특별시'),('B000211','서울동부','서울특별시'),('B000215','서울서부','서울특별시'),
  ('B000212','서울남부','서울특별시'),('B000213','서울북부','서울특별시'),('B000214','의정부','경기도'),
  ('B214807','고양','경기도'),('B214804','남양주','경기도'),('B000241','부천','경기도'),
  ('B000250','수원','경기도'),('B000251','성남','경기도'),('B000252','여주','경기도'),
  ('B000253','평택','경기도'),('B250826','안산','경기도'),('B000254','안양','경기도');

create table ref.regions (
  region_code   text primary key,        -- 법정동코드 10자리
  level         text not null,           -- sido / sigungu / dong
  sido          text,
  sigungu       text,
  eupmyeondong  text,
  sigungu_code  text,
  full_name     text
);

create table ref.stations (
  station_id    bigint generated always as identity primary key,
  name_ko       text not null,
  line_name     text,
  operator      text,
  geom          geography(point, 4326),
  closed_date   date
);
create index on ref.stations using gist (geom);

create table ref.rule_tables (
  rule_key      text not null,           -- small_lease_limit, acquisition_tax, ltv …
  valid_from    date not null,
  valid_to      date,
  value         jsonb not null,
  basis         text not null,           -- 근거 법령·고시
  primary key (rule_key, valid_from)
);

-- ───────── core: 정리된 자료 ─────────
create table core.cases (
  case_id       text primary key,        -- 법원코드-사건번호
  court_code    text not null references ref.courts(court_code),
  case_no       text not null,           -- 2025타경55580
  dept_name     text,                    -- 경매계
  claim_deadline date,                   -- 배당요구종기
  is_special_case boolean not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (court_code, case_no)
);

create table core.items (
  item_id       text primary key,        -- case_id-물건번호
  case_id       text not null references core.cases(case_id),
  item_no       int not null,
  doc_key       text,                    -- 법원 docid
  usage_name    text,
  usage_code    text,
  address       text,
  region_code   text,                    -- 법정동코드
  sido          text,
  sigungu       text,
  gu            text,
  lot_no        text,
  building_desc text,
  building_area_m2 numeric,
  appraisal_krw bigint,
  min_price_krw bigint,
  failed_count  int,
  sale_date     date,                    -- 다음(또는 마지막) 매각기일
  sale_place    text,
  status_code   text,
  note_masked   text,                    -- 비고(이름 가림)
  is_share      boolean not null default false,
  is_special_case boolean not null default false,
  geom          geography(point, 4326),
  display_policy ref.display_policy not null default 'public',
  source_id     text not null default 'court_items' references ref.sources(source_id),
  fetched_at    timestamptz,
  checked_at    timestamptz,
  updated_at    timestamptz not null default now(),
  unique (case_id, item_no)
);
create index on core.items (sale_date);
create index on core.items (region_code);
create index on core.items using gist (geom);

create table core.item_parts (
  item_part_id  text primary key,        -- item_id-목록번호
  item_id       text not null references core.items(item_id),
  part_no       int not null,
  part_kind     text,                    -- land / building / unit
  address       text,
  area_m2       numeric,
  pnu           text
);

create table core.rounds (
  round_id      text primary key,        -- item_id-YYYYMMDD
  item_id       text not null references core.items(item_id),
  sale_date     date not null,
  appraisal_krw bigint,
  min_price_krw bigint,
  failed_count  int,
  sale_place    text,
  result        text not null default 'scheduled'
                check (result in ('scheduled','sold','failed','changed','withdrawn','unknown')),
  fetched_at    timestamptz,
  checked_at    timestamptz
);
create index on core.rounds (item_id, sale_date);

create table core.sale_results (
  result_id     bigint generated always as identity primary key,
  court_code    text not null,
  case_no       text not null,
  item_no       int not null,
  sale_date     date not null,
  item_id       text,                    -- 우리 물건과 이어지면 채움
  usage_name    text,
  address       text,
  sido          text,
  region_code   text,
  building_area_m2 numeric,
  appraisal_krw bigint,
  min_price_krw bigint,
  winning_bid_krw bigint,
  sale_rate     numeric,                 -- 낙찰가/감정가 %
  failed_count  int,
  result        text not null check (result in ('sold','failed')),
  is_share      boolean not null default false,
  is_special_case boolean not null default false,
  origin        text not null,           -- 내부용: court_collect / court_db / supplement
  display_policy ref.display_policy not null default 'public',
  fetched_at    timestamptz,
  unique (court_code, case_no, item_no, sale_date)
);
create index on core.sale_results (sale_date);
create index on core.sale_results (region_code, usage_name);

create table core.documents (
  doc_id        text primary key,        -- case_id-종류-받은시각
  case_id       text not null references core.cases(case_id),
  doc_kind      text not null,
  version       int not null default 1,
  raw_id        bigint,                  -- raw.court_doc_raw
  checksum      text,
  source_date   date,
  fetched_at    timestamptz not null,
  display_policy ref.display_policy not null default 'public'
);
create index on core.documents (case_id, doc_kind, fetched_at desc);

create table core.extracted_fields (
  field_id      bigint generated always as identity primary key,
  doc_id        text not null references core.documents(doc_id),
  page          int,
  bbox          jsonb,
  field         text not null,
  raw_text      text,
  value         jsonb,
  method        text not null check (method in ('text','ocr','manual')),
  confidence    numeric check (confidence between 0 and 1),
  check_status  text not null default 'needs_review'
                check (check_status in ('auto_ok','needs_review','confirmed','rejected')),
  corrected_by  uuid,
  corrected_at  timestamptz,
  previous_value jsonb
);
create index on core.extracted_fields (doc_id);

create table core.rights (
  right_id      bigint generated always as identity primary key,
  case_id       text not null references core.cases(case_id),
  item_id       text references core.items(item_id),
  section       text,                    -- 갑구 / 을구
  rank_no       text,                    -- 순위번호
  purpose       text,                    -- 등기목적
  right_kind    text,                    -- 근저당, 가압류, 전세권 …
  receipt_date  date,
  receipt_no    bigint,
  amount_krw    bigint,
  holder_masked text,
  holder_raw    text,                    -- 내부용
  is_base_right boolean,
  source_field_id bigint references core.extracted_fields(field_id),
  fetched_at    timestamptz
);
create index on core.rights (case_id);

create table core.tenants (
  tenant_id     bigint generated always as identity primary key,
  case_id       text not null references core.cases(case_id),
  item_id       text references core.items(item_id),
  name_masked   text,
  name_raw      text,                    -- 내부용
  occupied_part text,
  move_in_date  date,
  fixed_date    date,
  claim_date    date,                    -- 배당요구일
  deposit_krw   bigint,
  monthly_rent_krw bigint,
  has_lease_registration boolean,
  source        text,                    -- spec_sheet / status_report / deliveries
  source_field_id bigint references core.extracted_fields(field_id),
  fetched_at    timestamptz
);
create index on core.tenants (case_id);

create table core.case_events (
  event_id      bigint generated always as identity primary key,
  case_id       text not null references core.cases(case_id),
  event_date    date,
  kind          text,                    -- 접수 / 송달
  category      text,                    -- 25분류
  importance    text,                    -- high / mid / low
  after_deadline boolean not null default false,
  text_masked   text,
  text_raw      text,                    -- 내부용
  fetched_at    timestamptz
);
create index on core.case_events (case_id, event_date);

create table core.trades (
  trade_id      bigint generated always as identity primary key,
  deal_kind     text not null check (deal_kind in ('sale','lease')),
  prop_type     text not null,           -- apt / rowhouse / officetel / house / commercial
  sub_type      text,
  sigungu_code  text,
  region_code   text,
  dong_name     text,
  complex_name  text,
  lot_no        text,
  area_m2       numeric,
  land_area_m2  numeric,
  floor         int,
  build_year    int,
  deal_date     date not null,
  price_krw     bigint,                  -- 매매
  deposit_krw   bigint,                  -- 전월세
  monthly_rent_krw bigint,
  contract_kind text,                    -- 신규 / 갱신
  prev_deposit_krw bigint,
  fetched_at    timestamptz
);
create index on core.trades (region_code, prop_type, deal_date);
create index on core.trades (complex_name, deal_date);

-- ───────── analysis: 계산 결과 ─────────
create table analysis.item_data_status (
  item_id       text not null references core.items(item_id),
  data_kind     text not null,           -- item, spec_sheet, status_report, deliveries, registry, building, trades …
  status        text not null default 'missing'
                check (status in ('missing','fetching','fetched','extracted','needs_review','verified','stale','error','restricted')),
  fetched_at    timestamptz,
  source_date   date,
  checked_at    timestamptz,
  computed_at   timestamptz,
  note          text,
  primary key (item_id, data_kind)
);

create table analysis.item_analysis (
  item_id       text not null references core.items(item_id),
  version       int not null,
  engine_version text not null,
  input_hash    text not null,
  result        jsonb not null,
  computed_at   timestamptz not null default now(),
  primary key (item_id, version)
);

create table analysis.risk_signals (
  signal_id     bigint generated always as identity primary key,
  item_id       text not null references core.items(item_id),
  rule_id       text not null,
  level         text not null check (level in ('fatal','high','mid','low','info')),
  status        text not null,           -- 확정 / 추정 / 확인 필요 / 모름
  title         text not null,
  evidence      jsonb,
  engine_version text not null,
  computed_at   timestamptz not null default now()
);
create index on analysis.risk_signals (item_id);

-- 새 표에도 API 계정 읽기 권한 정리(브라우저 계정은 접근 안 함)
revoke all on all tables in schema raw, ref, core, analysis from anon, authenticated;
