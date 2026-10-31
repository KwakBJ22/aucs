-- 사진 빼기(11/1): 법원 원문에 사진이 글자(base64)로 통째 들어 있어 raw.court_doc_raw 가 6GB → DB가 꽉 참(10/31).
-- 진행 중 물건 사진만 휴대폰 크기로 줄여 Storage(item-photos)에, 원문에서는 사진 글자를 뺌. 매각 뒤 30일 지나면 원문·사진 모두 지움(purge).
create table if not exists core.item_photos (
  case_id text not null references core.cases (case_id) on delete cascade,
  seq int not null,
  path text not null,
  width int,
  height int,
  bytes int,
  created_at timestamptz not null default now(),
  primary key (case_id, seq)
);
comment on table core.item_photos is '법원 현장 사진(휴대폰 크기로 줄여 Storage item-photos 에). 매각 뒤 30일 지나면 지움(purge).';
alter table core.item_photos enable row level security;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('item-photos', 'item-photos', true, 1048576, array['image/jpeg'])
on conflict (id) do nothing;

-- 원문에서 사진(picFile) 글자만 빼기 — 끝난 사건은 이것으로 바로 줄임
create or replace function raw.strip_pics(j jsonb) returns jsonb language sql immutable as $$
  select case jsonb_typeof(j)
    when 'object' then (select coalesce(jsonb_object_agg(k, raw.strip_pics(v)), '{}'::jsonb)
                        from jsonb_each(j) as e(k, v) where k <> 'picFile')
    when 'array' then (select coalesce(jsonb_agg(raw.strip_pics(v) order by n), '[]'::jsonb)
                       from jsonb_array_elements(j) with ordinality as e(v, n))
    else j end
$$;
