-- 0012 회원이 올린 등기부(결정 #5 1단계). 본인만(RLS). Supabase에 적용됨(10/18).
-- 원본 PDF는 delete_after(매각기일 + 30일)가 지나면 아침 묶음의 purge 작업이 pdf 칸을 비움 — 읽어 낸 권리(rights)만 남김.
-- 같은 물건을 보는 다른 손님에게 공유하지 않음.
create table if not exists app.uploaded_registries (
  upload_id     bigint generated always as identity primary key,
  user_id       uuid not null references auth.users(id) on delete cascade,
  item_id       text not null,
  file_name     text,
  pdf           bytea,
  sha256        text not null,
  status        text not null default 'processing' check (status in ('processing','parsed','failed')),
  method        text,            -- text(글자 PDF) / ocr(그림 PDF)
  rights        jsonb,           -- 읽어 낸 권리 목록(개인 권리자 이름은 가림)
  error         text,
  delete_after  date not null,
  created_at    timestamptz not null default now(),
  parsed_at     timestamptz
);
create index if not exists uploaded_registries_user_item on app.uploaded_registries (user_id, item_id, upload_id desc);
create index if not exists uploaded_registries_delete on app.uploaded_registries (delete_after) where pdf is not null;
alter table app.uploaded_registries enable row level security;
create policy uploaded_registries_select_own on app.uploaded_registries for select using (auth.uid() = user_id);
create policy uploaded_registries_write_own on app.uploaded_registries for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
grant select, insert, update, delete on app.uploaded_registries to authenticated;
