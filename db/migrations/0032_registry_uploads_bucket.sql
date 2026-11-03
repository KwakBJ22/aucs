-- 등기부 PDF 를 화면에서 파일 보관함에 바로 올림(11/3 — Vercel API 는 한 번에 4.5MB 까지만 받음). 코워크가 적용함.
-- API 가 받아 간 뒤 바로 지움. 회원은 자기 폴더(registry-uploads/<회원 id>/…)에만 올릴 수 있음.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('registry-uploads', 'registry-uploads', false, 10485760, array['application/pdf'])
on conflict (id) do nothing;
create policy registry_uploads_insert_own on storage.objects for insert to authenticated
  with check (bucket_id = 'registry-uploads' and (storage.foldername(name))[1] = auth.uid()::text);
