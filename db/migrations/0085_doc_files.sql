-- 법원 서류 원본 파일(11/27 대표님 — 「원본이 없어 제대로 분석을 못 하고 있다」): 매각물건명세서 · 현황조사서.
-- 법원이 기일마다 명세서는 7일 · 현황조사서는 14일만 열어 두므로, 받을 때 원본을 그대로 보관.
-- 판(명세서는 기일마다 다시 씀 · 정정도 있음)마다 한 줄 — 같은 파일(sha256)은 한 번만.
-- 손님 화면은 API 가 확인 뒤 내줌(실명이 들어 있어 공개 보관함이 아님 · 끝난 사건은 보이지 않음).
create table if not exists core.doc_files (
  file_id bigint generated always as identity primary key,
  case_id text not null references core.cases (case_id) on delete cascade,
  item_no int,                                   -- 명세서는 물건마다, 현황조사서는 사건 하나면 null
  kind text not null check (kind in ('spec', 'status_report')),
  source text not null check (source in ('court', 'upload')),  -- 법원에서 받음 / 관리자가 올림
  path text not null,                            -- Storage court-docs 안 경로
  sha256 text not null,
  written_on date,                               -- 명세서 작성일(판) — 알 때만
  sale_date date,                                -- 어느 기일 판인지(받을 때의 매각기일)
  pages int,
  bytes int,
  created_at timestamptz not null default now(),
  unique (case_id, kind, sha256)
);
create index if not exists doc_files_case on core.doc_files (case_id, kind, created_at desc);
comment on table core.doc_files is '법원 서류 원본(명세서 · 현황조사서) — Storage court-docs(비공개). 11/27';
alter table core.doc_files enable row level security;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('court-docs', 'court-docs', false, 52428800, array['application/pdf', 'text/html', 'application/json'])
on conflict (id) do nothing;
