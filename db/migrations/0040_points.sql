-- 0040 포인트 벌기(11/12 대표님, docs/design/11-points.md): 손님이 등기부·감정평가서를 올리면 포인트, 올린 서류는 모든 회원이 같이 봄.

-- 값(바뀔 수 있는 숫자)은 기준표에
insert into ref.rule_tables (rule_key, valid_from, value, basis) values
('points', '2026-11-01',
 '{"registry": 1000, "appraisal": 500, "daily_max": {"registry": 5, "appraisal": 5},
   "hold_minutes": 10, "hold_extend_minutes": 10, "expire_days": 365, "registry_fresh_days": 30}'::jsonb,
 '11/12 대표님: 등기부는 손님이 돈 내고 뗌 1,000P · 감정평가서는 법원 무료 500P · 각각 하루 5건 · 맡기기 10분(+10분 한 번) · 1년')
on conflict do nothing;

-- 포인트 원장: 받기(+) · 쓰기(−) 한 줄씩. 잔액 = 기한 안 받은 것 + 쓴 것
create table if not exists app.point_ledger (
  entry_id    bigint generated always as identity primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  delta       int not null,
  reason      text not null check (reason in ('registry','appraisal','spend','refund','admin')),
  item_id     text,
  ref_id      bigint,                 -- 올린 서류(app.contrib_uploads) 또는 결제(app.payments)
  expires_at  timestamptz,            -- 받은 포인트만
  created_at  timestamptz not null default now()
);
create index if not exists point_ledger_user on app.point_ledger (user_id, created_at desc);

-- 올린 서류 한 건 = 한 줄(포인트를 줬는지·왜 안 줬는지)
create table if not exists app.contrib_uploads (
  contrib_id   bigint generated always as identity primary key,
  user_id      uuid not null references auth.users(id) on delete cascade,
  item_id      text not null,
  case_id      text not null,
  kind         text not null check (kind in ('registry','appraisal')),
  registry_upload_id bigint references app.uploaded_registries(upload_id) on delete set null,
  sha256       text not null,
  status       text not null default 'checking' check (status in ('checking','ok','review','rejected')),
  points       int not null default 0,
  note         text,                  -- 포인트 안 준 까닭 등(화면 한 줄)
  created_at   timestamptz not null default now(),
  decided_at   timestamptz
);
create index if not exists contrib_uploads_user_day on app.contrib_uploads (user_id, kind, created_at desc);
create index if not exists contrib_uploads_case on app.contrib_uploads (case_id, kind, status);
create unique index if not exists contrib_uploads_once on app.contrib_uploads (kind, sha256);

-- 맡기기: 물건 · 서류마다 한 사람이 잠깐
create table if not exists app.contrib_holds (
  item_id   text not null,
  kind      text not null check (kind in ('registry','appraisal')),
  user_id   uuid not null references auth.users(id) on delete cascade,
  until_at  timestamptz not null,
  extended  boolean not null default false,
  primary key (item_id, kind)
);

-- 등기부: 주소가 맞으면 모든 회원이 같이 봄(11/12 — 전엔 올린 사람만)
alter table app.uploaded_registries add column if not exists shared boolean not null default false;
create index if not exists uploaded_registries_shared on app.uploaded_registries (item_id, upload_id desc) where shared;
comment on column app.uploaded_registries.shared is '주소가 물건과 맞아 다른 회원도 같이 봄(11/12)';

-- 결제 때 쓴 포인트(결제창을 붙일 때 채움)
alter table app.payments add column if not exists points_used int not null default 0;

-- 감정평가서를 화면에서 바로 올리는 보관함(크기가 커서 API 를 거치지 않음 — 등기부와 같은 방식). 회원은 자기 폴더에만.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('appraisal-uploads', 'appraisal-uploads', false, 62914560, array['application/pdf'])
on conflict (id) do nothing;
drop policy if exists appraisal_uploads_insert_own on storage.objects;
create policy appraisal_uploads_insert_own on storage.objects for insert to authenticated
  with check (bucket_id = 'appraisal-uploads' and (storage.foldername(name))[1] = auth.uid()::text);

alter table app.point_ledger enable row level security;
alter table app.contrib_uploads enable row level security;
alter table app.contrib_holds enable row level security;
