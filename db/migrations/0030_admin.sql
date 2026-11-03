-- 관리자 모드 1단계(11/2): 관리자 표·작업 요청·이용권·문의·공지·신호 판단·기준표 검토 (코워크가 적용함)
create table if not exists app.admins (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('owner','operator','viewer')),
  added_by uuid,
  added_at timestamptz not null default now()
);
-- 처음 관리자: 대표 계정(owner)
alter table ops.audit_log add column if not exists note text;
create or replace function ops.audit_no_change() returns trigger language plpgsql as $$
begin raise exception '감사 기록은 고치거나 지울 수 없어요'; end $$;
drop trigger if exists audit_lock on ops.audit_log;
create trigger audit_lock before update or delete on ops.audit_log for each row execute function ops.audit_no_change();
create table if not exists ops.job_requests (
  req_id bigint generated always as identity primary key, job_key text not null, requested_by uuid,
  requested_at timestamptz not null default now(),
  status text not null default 'waiting' check (status in ('waiting','running','done','failed')),
  started_at timestamptz, finished_at timestamptz, message text);
create index if not exists job_requests_wait on ops.job_requests (status, requested_at);
create table if not exists app.grants (
  grant_id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  plan text not null, until_date date not null, reason text not null, granted_by uuid,
  created_at timestamptz not null default now());
create index if not exists grants_user on app.grants (user_id, until_date);
create table if not exists app.user_limits (
  user_id uuid primary key references auth.users(id) on delete cascade,
  reason text not null, limited_by uuid, created_at timestamptz not null default now());
create table if not exists app.inquiries (
  inquiry_id bigint generated always as identity primary key,
  user_id uuid references auth.users(id) on delete set null,
  body text not null check (length(body) between 2 and 2000),
  answer text, answered_by uuid, answered_at timestamptz, created_at timestamptz not null default now());
create index if not exists inquiries_open on app.inquiries (answered_at, created_at);
create table if not exists app.notices (
  notice_id bigint generated always as identity primary key, title text not null, body text not null default '',
  start_at timestamptz not null default now(), end_at timestamptz, pinned boolean not null default false,
  created_by uuid, created_at timestamptz not null default now());
create table if not exists analysis.signal_overrides (
  item_id text not null, rule_id text not null, status text not null check (status in ('확정','없음')),
  decided_by uuid, decided_at timestamptz not null default now(), primary key (item_id, rule_id));
alter table ref.rule_tables add column if not exists reviewed_at timestamptz;
alter table ref.rule_tables add column if not exists reviewed_by uuid;
alter table app.admins enable row level security;
alter table app.grants enable row level security;
alter table app.user_limits enable row level security;
alter table app.inquiries enable row level security;
alter table app.notices enable row level security;
alter table ops.job_requests enable row level security;
alter table analysis.signal_overrides enable row level security;
