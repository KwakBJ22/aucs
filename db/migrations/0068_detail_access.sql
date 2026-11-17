-- 물건 상세 열람 권한 · 횟수 한도(11/17 대표님). 코드: apps/api services/access.py
-- 오픈 전(free_period true): 로그인하면 전부 무료. 오픈하는 날 free_period 를 false 로 바꾼 줄을 새로 넣으면
-- 가입 뒤 24시간 무료 → 그 뒤는 이용권. 1분 30건 · 하루 500건은 보면서 조절(대표님).
insert into ref.rule_tables (rule_key, valid_from, value, basis) values
('access', '2026-11-01',
 '{"free_period": true, "trial_hours": 24, "per_min": 30, "per_day": 500}'::jsonb,
 '11/17 대표님: 상세는 로그인 · 오픈 전 로그인하면 무료 · 오픈 뒤 가입하고 하루 무료 뒤 결제. 로봇 막기 1분 30건 · 하루 500건(보면서 조절)')
on conflict do nothing;

-- 상세 연 기록(서버가 남김 — 화면이 보내는 app.events 와 따로). 3개월 지나면 purge 가 지움(접속 기록 3개월).
create table if not exists app.detail_views (
  view_id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  item_id text,
  at timestamptz not null default now()
);
create index if not exists detail_views_user_at on app.detail_views (user_id, at desc);
create index if not exists detail_views_at on app.detail_views (at);
alter table app.detail_views enable row level security;
