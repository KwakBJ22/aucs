-- 이용권 결제·환불 요청(11/3, 코워크가 적용함). 토스페이먼츠를 붙이면 결제 승인 때 한 줄씩 들어옴.
-- 결제 기록은 5년 보관(전자상거래법) → 회원 탈퇴 때 회원 번호만 비움(on delete set null).
create table if not exists app.payments (
  payment_id bigint generated always as identity primary key,
  user_id uuid references auth.users(id) on delete set null,
  plan text not null check (plan in ('personal','pro','one')),
  period text not null check (period in ('month','year','one')),
  amount_krw bigint not null check (amount_krw >= 0),
  item_id text,
  status text not null default 'paid' check (status in ('paid','cancelled','refunded','part_refunded')),
  refunded_krw bigint not null default 0,
  auto_renew boolean not null default false,
  method_note text,
  order_id text unique,
  receipt_url text,
  paid_at timestamptz not null default now(),
  valid_from date not null default current_date,
  valid_to date not null,
  created_at timestamptz not null default now()
);
create index if not exists payments_user on app.payments (user_id, paid_at desc);
create table if not exists app.refund_requests (
  request_id bigint generated always as identity primary key,
  payment_id bigint not null references app.payments(payment_id),
  user_id uuid references auth.users(id) on delete set null,
  estimate_krw bigint not null,
  reason text,
  status text not null default 'waiting' check (status in ('waiting','done','rejected')),
  answer text,
  decided_by uuid,
  decided_at timestamptz,
  created_at timestamptz not null default now()
);
create unique index if not exists refund_one_waiting on app.refund_requests (payment_id) where status = 'waiting';
alter table app.payments enable row level security;
alter table app.refund_requests enable row level security;
