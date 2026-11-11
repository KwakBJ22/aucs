-- 0042 사건 서류(현황조사·문건송달)를 마지막으로 물어본 날(11/12) — 내용이 같아 raw 에 새 줄이 안 생겨도
-- 「물어봤음」을 남겨, 서류 보관이 같은 사건을 매시간 다시 묻지 않게 함.
alter table core.cases add column if not exists docs_checked_at timestamptz;
comment on column core.cases.docs_checked_at is '서류 보관(court_docs --archive)이 현황조사·문건송달을 마지막으로 물어본 때';
