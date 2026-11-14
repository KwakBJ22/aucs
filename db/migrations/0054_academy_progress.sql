-- 0054 옥스아카데미 진도를 계정에(11/14 대표님): 들은 수업 · 해 본 과제를 회원마다 적어 둠.
-- 예전엔 기기에만 적어, 다른 기기에서 열면 처음부터로 보였음. 탈퇴하면 함께 지워짐.
create table if not exists app.academy_progress (
  user_id uuid not null references auth.users(id) on delete cascade,
  key     text not null,                 -- 수업 열쇠(「what」) 또는 과제(「task:find」)
  done_at timestamptz not null default now(),
  primary key (user_id, key)
);
comment on table app.academy_progress is '옥스아카데미에서 들은 수업 · 해 본 과제(회원마다). 화면이 기기 진도와 합쳐서 씀(11/14).';
alter table app.academy_progress enable row level security;
