-- 0053 미리 나눠 둔 모아 보기(11/14): 열 때마다 물건 2만 줄을 받아 그 자리에서 모음에 나누던 것을,
-- 분석이 끝날 때마다 수집기(jobs/pick_scores)가 한 번 나눠 두고 화면은 읽기만 하게.
-- 분석 결과에서 다시 만들 수 있는 표 — 수집기가 매번 비우고 새로 채움. 공개 자료라 API(관리자 연결)만 읽음.
create table if not exists analysis.collection_items (
  key         text not null,               -- cheap · safe · rising · next · station · special (COLLECT-01)
  item_id     text not null,
  why         text not null,               -- 이 모음에 든 이유 한 줄
  sort        double precision not null,   -- 모음 안 순서(큰 것이 앞)
  computed_at timestamptz not null default now(),
  primary key (key, item_id)
);
create index if not exists collection_items_item on analysis.collection_items (item_id);
comment on table analysis.collection_items is '미리 나눠 둔 모아 보기(COLLECT-01 · WAIT-01). pick_scores 작업이 분석 뒤마다 다시 채움(11/14).';
alter table analysis.collection_items enable row level security;
