-- 감정평가서 원본 PDF(11/11 대표님 — 다른 업체처럼 원본 그대로 손님에게 보임).
-- 대표님이 받아 둔 PDF 를 appraisal_folder 수집기가 Storage(appraisal-pdfs)에 올리고 여기에 적음. 상세 화면 「감정평가서 원본 보기」가 읽음.
create table if not exists core.appraisal_files (
  case_id text primary key references core.cases (case_id) on delete cascade,
  appraisal_no text,
  path text not null,
  firm text,
  pages int,
  bytes int,
  created_at timestamptz not null default now()
);
comment on table core.appraisal_files is '감정평가서 원본 PDF(Storage appraisal-pdfs). 대표님이 받아 둔 폴더에서 appraisal_folder 가 올림(11/11).';
alter table core.appraisal_files enable row level security;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('appraisal-pdfs', 'appraisal-pdfs', true, 52428800, array['application/pdf'])
on conflict (id) do nothing;
