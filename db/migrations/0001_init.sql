-- 0001 처음 구조: 스키마 6개, 확장, 원천 목록, 작업 기록, 회원 프로필
-- 사건·물건·문서 등 본 표는 1단계 0002부터 추가합니다.

create extension if not exists postgis;
create extension if not exists pgcrypto;

create schema if not exists raw;       -- 받은 그대로 (추가만)
create schema if not exists ref;       -- 기준표
create schema if not exists core;      -- 정리된 자료
create schema if not exists analysis;  -- 계산 결과
create schema if not exists app;       -- 사용자 자료 (RLS)
create schema if not exists ops;       -- 수집·작업·관리자 기록

-- 외부 표시 구분
create type ref.display_policy as enum ('public', 'owner_only', 'internal', 'blocked');

-- 원천 목록·이용조건
create table ref.sources (
  source_id        text primary key,
  name_ko          text not null,
  basis_url        text,
  checked_date     date,
  redistributable  boolean not null default false,
  display_policy   ref.display_policy not null default 'internal',
  retention_note   text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
comment on table ref.sources is '원천 목록과 이용조건';

insert into ref.sources (source_id, name_ko, display_policy, redistributable, retention_note) values
  ('court_items',    '법원경매정보 물건상세', 'public',   true,  '출처 표시, 저작권법 제24조의2'),
  ('court_docs',     '법원 문서(명세서·현황조사서·문건송달·기일)', 'public', true, '열람 기간 안에 받아 보관'),
  ('court_appraisal','법원 감정평가서', 'internal', false, '협회 확인 전 숨김'),
  ('court_results',  '법원 매각결과', 'public', true, '최근 1주만 보임 → 매일 수집'),
  ('trades',         '국토부 실거래(매매·전월세)', 'public', true, null),
  ('buildings',      '건축물대장', 'public', true, null),
  ('price_notice',   '공시가격', 'public', true, null),
  ('land_use',       '토지이용계획(vworld)', 'public', true, null),
  ('redev',          '정비사업(서울)', 'public', true, null),
  ('kapt',           '공동주택관리정보(K-apt)', 'public', true, null),
  ('regions',        '법정동코드', 'public', true, null),
  ('user_registry',  '사용자 업로드 등기부', 'owner_only', false, '탈퇴 시 삭제'),
  ('user_field',     '사용자 임장 기록', 'owner_only', false, '탈퇴 시 삭제'),
  ('user_bid',       '사용자 입찰 결과 기록', 'internal', false, '이름 없는 통계만 공개');

-- 작업
create table ops.jobs (
  job_id      text primary key,
  name_ko     text not null,
  schedule    text,              -- cron 식
  enabled     boolean not null default true,
  created_at  timestamptz not null default now()
);

create table ops.job_runs (
  run_id       bigint generated always as identity primary key,
  job_id       text not null references ops.jobs(job_id),
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  status       text not null default 'running' check (status in ('running','ok','failed','stopped')),
  item_count   integer,
  message      text
);
create index on ops.job_runs (job_id, started_at desc);

-- 수집 기록 (요청 한 건마다)
create table ops.fetch_log (
  fetch_id     bigint generated always as identity primary key,
  source_id    text not null references ref.sources(source_id),
  run_id       bigint references ops.job_runs(run_id),
  target       text,
  http_status  integer,
  fetched_at   timestamptz not null default now(),
  checksum     text,
  note         text
);
create index on ops.fetch_log (source_id, fetched_at desc);

-- 관리자 변경 기록
create table ops.audit_log (
  audit_id    bigint generated always as identity primary key,
  actor_id    uuid,
  action      text not null,
  target      text,
  before_val  jsonb,
  after_val   jsonb,
  at          timestamptz not null default now()
);

-- 회원 프로필 (로그인 계정은 Supabase auth.users)
create table app.profiles (
  user_id          uuid primary key references auth.users(id) on delete cascade,
  nickname         text,
  interest_regions text[] not null default '{}',   -- 법정동코드
  cash_krw         bigint,
  purpose          text check (purpose in ('live','invest')),
  role             text not null default 'member' check (role in ('member','admin')),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
comment on table app.profiles is '회원 프로필: 관심 지역·가진 현금·목적(실거주/투자)';

alter table app.profiles enable row level security;
create policy profiles_select_own on app.profiles for select using (auth.uid() = user_id);
create policy profiles_insert_own on app.profiles for insert with check (auth.uid() = user_id);
create policy profiles_update_own on app.profiles for update using (auth.uid() = user_id) with check (auth.uid() = user_id and role = 'member');

-- 기능 켜기·끄기 (관리자만 바꿈, API가 서버 키로 읽음)
create table app.feature_flags (
  flag_key    text primary key,
  enabled     boolean not null default false,
  note        text,
  updated_at  timestamptz not null default now()
);
alter table app.feature_flags enable row level security;
insert into app.feature_flags (flag_key, enabled, note) values
  ('show_appraisal_report', false, '감정평가서 표시 — 협회 확인 전 꺼 둠');

-- 브라우저(anon·authenticated)는 app.profiles만, 나머지 스키마는 API(서버 키)만
revoke all on schema raw, ref, core, analysis, ops from anon, authenticated;
grant usage on schema app to authenticated;
grant select, insert, update on app.profiles to authenticated;
