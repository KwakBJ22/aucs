-- 예정물건 3단계(11/28 대표님 「진행해요」 — 경매개시 알림).
-- 하트(사건 하나)만이 아니라 「동네」 · 「단지」로 걸어 두면, 그곳에 새 사건(배당요구종기공고)이 들어올 때 알림.
-- ① 동네: 사람마다 시군구 목록 하나(곧 나올 물건 「내 지역」 그대로) — 하루 한 번 묶어서 「강서구 외 1곳에 곧 나올 물건 N건」.
-- ② 단지: 물건 상세 「같은 단지」 칸에서 켬 — 같은 지역 코드 + 지번에 새 사건(공고 전)이나 새 매각공고 물건이 들어오면 한 건씩.
--    세입자가 사는 집을 지키는 「내 집 지키기」도 이 표를 씀(다음 차례).
-- 처음 받은 공고(11/27 8,507건)로 알림이 쏟아지지 않게, 걸어 둔 때(created_at) 뒤에 처음 본 사건만.

create table if not exists app.upcoming_areas (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  sigungu     text[] not null,
  created_at  timestamptz not null default now(),
  checked_at  timestamptz not null default now()   -- 이때 뒤에 처음 본 사건만 알림
);
comment on table app.upcoming_areas is '곧 나올 물건 동네 알림(시군구) — 11/28';
alter table app.upcoming_areas enable row level security;

create table if not exists app.lot_watches (
  user_id      uuid not null references auth.users (id) on delete cascade,
  region_code  text not null,
  lot_no       text not null,
  label        text,                               -- 「서초구 반포동 20-43 래미안」
  created_at   timestamptz not null default now(),
  checked_at   timestamptz not null default now(),
  primary key (user_id, region_code, lot_no)
);
create index if not exists lot_watches_lot on app.lot_watches (region_code, lot_no);
comment on table app.lot_watches is '단지(지역 코드 + 지번) 경매 알림 — 새 공고 전 사건 · 새 매각공고. 11/28';
alter table app.lot_watches enable row level security;
