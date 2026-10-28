-- 0025 공매 알림·같은 집 연결 (10/28, MCP로 적용)
alter table core.onbid_items add column if not exists first_seen_at timestamptz not null default now();
comment on column core.onbid_items.first_seen_at is '처음 받은 때 — 저장한 조건의 「새 공매」 알림 기준(바꾸지 않음)';

create table if not exists core.item_links (
  court_item_id text not null,
  onbid_item_id text not null references core.onbid_items (item_id) on delete cascade,
  matched_at    timestamptz not null default now(),
  primary key (court_item_id, onbid_item_id)
);
create index if not exists item_links_onbid_idx on core.item_links (onbid_item_id);
alter table core.item_links enable row level security;
comment on table core.item_links is '같은 집이 법원 경매·공매에 함께 나온 것 — 법정동·지번이 같고 동·호수까지 맞을 때만(0025)';
