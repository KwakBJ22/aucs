-- 0045 관리자 알림 보내기 · 빨간 불 휴대폰 알림(11/12 대표님 「나머지 이어서」, 관리자 기능명세서 2단계)

-- 알림 보내기: 관리자가 쓰고(바로 또는 예약), PC 의 관리자_요청(5분마다)이 때가 되면 알림함에 넣고 휴대폰으로 보냄.
-- 밤 9시~아침 8시에는 보내지 않음(기다렸다 아침에). 광고성 알림은 보내지 않음(정보통신망법 — 수신 동의 전).
create table if not exists app.broadcasts (
  bc_id      bigint generated always as identity primary key,
  title      text not null check (length(title) between 2 and 60),
  body       text not null default '' check (length(body) <= 300),
  link       text,                                  -- 누르면 갈 곳(우리 주소만, 예: /points)
  target     jsonb not null default '{"kind":"all"}', -- all · region(시군구 이름들) · paid · free
  send_at    timestamptz not null default now(),
  status     text not null default 'waiting' check (status in ('waiting','sent','cancelled')),
  sent_n     int,
  sent_at    timestamptz,
  created_by uuid,
  created_at timestamptz not null default now()
);
create index if not exists broadcasts_due on app.broadcasts (status, send_at);
alter table app.broadcasts enable row level security;

-- 빨간 불 휴대폰 알림: 같은 빨간 불은 하루 한 번만 보냄
create table if not exists ops.admin_alerts (
  alert_key text not null,
  day       date not null default (now() at time zone 'Asia/Seoul')::date,
  text      text not null,
  created_at timestamptz not null default now(),
  primary key (alert_key, day)
);
alter table ops.admin_alerts enable row level security;
