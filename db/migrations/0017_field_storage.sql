-- 0017 현장 체크 사진·음성: 비공개 저장소 'field', 경로 {user_id}/{item_id}/파일. 본인 폴더만 읽고 쓰고 지움. 파일 하나 10MB까지, 사진·소리만. MCP로 적용(10/19).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('field', 'field', false, 10485760, array['image/jpeg','image/png','image/webp','audio/webm','audio/mp4','audio/mpeg','audio/ogg'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

create policy field_select_own on storage.objects for select to authenticated
  using (bucket_id = 'field' and (storage.foldername(name))[1] = auth.uid()::text);
create policy field_insert_own on storage.objects for insert to authenticated
  with check (bucket_id = 'field' and (storage.foldername(name))[1] = auth.uid()::text);
create policy field_delete_own on storage.objects for delete to authenticated
  using (bucket_id = 'field' and (storage.foldername(name))[1] = auth.uid()::text);
