-- 0009 내 입찰 결과(RESULT-01)·낙찰 후 일정(SCHED-01) 기록. 본인만(RLS). Supabase에 적용됨(10/17).
-- 남에게는 통계로만 공개(법원·용도·회차별 응찰자 수·2위 금액 차이). 개인 줄은 공개하지 않음.

create table if not exists app.bid_results (
  bid_id          bigint generated always as identity primary key,
  user_id         uuid not null references auth.users(id) on delete cascade,
  item_id         text not null,
  sale_date       date not null,
  outcome         text not null check (outcome in ('won','lost','not_bid','cancelled')),
  my_bid_krw      bigint check (my_bid_krw is null or my_bid_krw > 0),
  winning_bid_krw bigint check (winning_bid_krw is null or winning_bid_krw > 0),
  second_bid_krw  bigint check (second_bid_krw is null or second_bid_krw > 0),
  bidder_count    int check (bidder_count is null or bidder_count >= 0),
  pay_date        date,            -- 잔금 낸 날(또는 낼 날) — 일정표 기준
  memo            text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (user_id, item_id, sale_date)
);
create index if not exists bid_results_item on app.bid_results (item_id);

alter table app.bid_results enable row level security;
create policy bid_results_select_own on app.bid_results for select using (auth.uid() = user_id);
create policy bid_results_write_own on app.bid_results for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
grant select, insert, update, delete on app.bid_results to authenticated;
