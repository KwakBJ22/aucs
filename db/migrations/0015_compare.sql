-- 0015 비교함: 관심 물건 중 비교에 넣은 것 + 비교에서 뺀 이유(다음 추천에서 덜 보여 주기). 본인만(RLS). MCP로 적용(10/19).
alter table app.watch_items add column if not exists in_compare boolean not null default false;

create table if not exists app.compare_exclusions (
  user_id    uuid not null references auth.users(id) on delete cascade,
  item_id    text not null,
  reason     text not null check (reason in ('budget','assumed_unclear','field_bad','other')),
  created_at timestamptz not null default now(),
  primary key (user_id, item_id)
);
alter table app.compare_exclusions enable row level security;
create policy compare_exclusions_select_own on app.compare_exclusions for select using (auth.uid() = user_id);
create policy compare_exclusions_write_own on app.compare_exclusions for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
grant select, insert, update, delete on app.compare_exclusions to authenticated;
