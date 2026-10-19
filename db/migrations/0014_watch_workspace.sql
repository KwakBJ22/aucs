-- 0014: 물건 작업 공간(WATCH-02) — 내 확인 체크·저장한 입찰가 (10/19, MCP로 적용함)
alter table app.watch_items
  add column if not exists checks jsonb not null default '{}'::jsonb,
  add column if not exists calcs jsonb not null default '[]'::jsonb,
  add column if not exists updated_at timestamptz not null default now();
comment on column app.watch_items.checks is '체크리스트 항목 key → 내가 확인한 날(YYYY-MM-DD)';
comment on column app.watch_items.calcs is '저장한 입찰가 [{bid_krw, cash_krw, saved_at}] 최대 5개';
