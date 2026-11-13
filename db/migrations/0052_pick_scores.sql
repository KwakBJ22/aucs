-- 0052 미리 매겨 둔 추천 점수(11/14): 홈을 열 때마다 물건 4,000줄을 받아 서버에서 점수를 매기던 것을,
-- 분석이 끝날 때마다 수집기(jobs/pick_scores)가 한 번 매겨 두고 홈은 읽기만 하게.
-- 분석 결과에서 다시 만들 수 있는 표 — 수집기가 매번 비우고 새로 채움. 공개 자료라 API(관리자 연결)만 읽음.
create table if not exists analysis.pick_scores (
  purpose      text not null,              -- '' (로그인 전 · 목적 없음) · live · rent · invest
  item_id      text not null,
  score        int not null,               -- PICK-01 점수(0~100) — 걸러진 물건은 안 넣음
  reasons      jsonb not null default '[]',
  likely_fail  boolean not null default false,  -- 유찰 예상(WAIT-01)
  fail_odds    jsonb,                      -- {fail, n, pct, of10, likely, scope}
  next_min_krw bigint,                     -- 유찰되면 다음 최저가
  computed_at  timestamptz not null default now(),
  primary key (purpose, item_id)
);
create index if not exists pick_scores_item on analysis.pick_scores (item_id);
comment on table analysis.pick_scores is '미리 매겨 둔 추천 점수(PICK-01 · WAIT-01). pick_scores 작업이 분석 뒤마다 다시 채움(11/14).';
alter table analysis.pick_scores enable row level security;
