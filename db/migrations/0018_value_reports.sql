-- 0018 「이 값이 틀렸어요」 제보(DOC-01 → ADM-01 검증 대기). 회원은 자기 제보만 봄(RLS), 관리자 화면은 API(관리자 연결)로 읽음.
-- MCP로 적용(10/27).
create table if not exists app.value_reports (
  report_id  bigint generated always as identity primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  item_id    text not null,
  section    text not null check (char_length(section) <= 40),   -- 어느 칸(무엇을 사나·떠안나·얼마짜리·원문 등)
  note       text not null check (char_length(note) between 1 and 500),
  status     text not null default 'open' check (status in ('open', 'fixed', 'rejected')),
  created_at timestamptz not null default now(),
  closed_at  timestamptz
);
create index if not exists value_reports_open_idx on app.value_reports (status, created_at desc);
alter table app.value_reports enable row level security;
create policy value_reports_select_own on app.value_reports for select using (auth.uid() = user_id);
create policy value_reports_insert_own on app.value_reports for insert with check (auth.uid() = user_id);
grant select, insert on app.value_reports to authenticated;
