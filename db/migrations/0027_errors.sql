-- 오류 기록(출시 전 꼭, 10/29): 화면(web)·API 오류를 한곳에. 관리자 「오류」에서 봄. 90일 지나면 지움.
create table if not exists ops.errors (
  error_id bigserial primary key,
  at timestamptz not null default now(),
  side text not null check (side in ('web', 'api')),
  path text,
  message text not null,
  stack text,
  anon_id text,
  agent text
);
create index if not exists errors_at on ops.errors (at desc);
comment on table ops.errors is '오류 기록(출시 전 꼭): 화면(web)·API 오류. 90일 지나면 지움(아침 묶음).';
