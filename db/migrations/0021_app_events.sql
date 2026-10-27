-- 0021 사용 기록(할 일 5): 성공 지표(처음 판단까지 시간·관심 등록률·주간 재방문)를 재려고 화면 이동·주요 동작만 남김.
-- 이름·이메일은 남기지 않음(기기마다 무작위 anon_id, 로그인했으면 user_id). API(관리자 연결)만 씀. MCP로 적용(10/27).
create table if not exists app.events (
  event_id  bigint generated always as identity primary key,
  at        timestamptz not null default now(),
  anon_id   text not null check (char_length(anon_id) <= 40),
  user_id   uuid references auth.users(id) on delete set null,
  kind      text not null check (char_length(kind) <= 30),
  path      text check (char_length(path) <= 200),
  item_id   text check (char_length(item_id) <= 80)
);
create index if not exists events_at_idx on app.events (at);
create index if not exists events_anon_idx on app.events (anon_id, at);
alter table app.events enable row level security;
