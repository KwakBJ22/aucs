-- 0016 모의입찰과 복기: 입찰하지 않아도 예상 입찰가·상한·이유를 남기고 결과 뒤 돌아봄. 본인만(RLS). 적중률 순위는 만들지 않음. MCP로 적용(10/19).
create table if not exists app.mock_bids (
  mock_id    bigint generated always as identity primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  item_id    text not null,
  sale_date  date not null,
  decision   text not null check (decision in ('bid','skip')),
  bid_krw    bigint check (bid_krw is null or bid_krw > 0),
  max_krw    bigint check (max_krw is null or max_krw > 0),
  reason     text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, item_id, sale_date)
);
alter table app.mock_bids enable row level security;
create policy mock_bids_select_own on app.mock_bids for select using (auth.uid() = user_id);
create policy mock_bids_write_own on app.mock_bids for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
grant select, insert, update, delete on app.mock_bids to authenticated;
