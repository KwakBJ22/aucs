-- 0075 결제 전·후 미리 구성(11/23 대표님 「결제 붙이면 돌아가게 미리」).
-- 토스페이먼츠 키를 넣기 전에는 아무도 쓰지 않는 표 — 지우는 것 없음.
--  · app.pay_orders   : 결제창을 열기 전에 서버가 만든 주문(금액은 서버가 정함 · 승인 때 맞춰 봄)
--  · app.billing_cards: 매달 자동결제 카드(토스 빌링키 — 서버만 읽음, 화면에는 「신한 1234」만)
--  · app.payments 에 토스 결제 번호(payment_key) · 매달 자동결제 실패 횟수(renew_fails)

create table if not exists app.pay_orders (
  order_id      text primary key,                    -- 토스 orderId(6~64자, 영문 · 숫자 · - _ =)
  user_id       uuid references auth.users(id) on delete set null,
  plan          text not null check (plan in ('personal','pro','one')),
  period        text not null check (period in ('month','year','one')),
  item_id       text,                                -- 한 건 이용권의 물건
  amount_krw    bigint not null check (amount_krw > 0),
  order_name    text not null,
  method        text,                                -- 고른 수단(card · bank · vbank · toss · naver · kakao · billing)
  status        text not null default 'ready'
                check (status in ('ready','waiting','paid','failed','cancelled','expired')),
  payment_key   text,
  deposit_secret text,                               -- 입금 전용 계좌 웹훅 맞춰 보기(토스 secret)
  vbank         jsonb,                               -- 입금 안내(은행 코드 · 계좌 · 기한)
  fail_code     text,
  fail_msg      text,
  payment_id    bigint references app.payments(payment_id),
  renew_of      bigint references app.payments(payment_id),  -- 매달 자동결제면 앞 결제
  created_at    timestamptz not null default now(),
  done_at       timestamptz
);
create index if not exists pay_orders_user on app.pay_orders (user_id, created_at desc);
create unique index if not exists pay_orders_renew_once on app.pay_orders (renew_of)
  where renew_of is not null and status in ('ready','paid');

create table if not exists app.billing_cards (
  user_id      uuid primary key references auth.users(id) on delete cascade,
  customer_key text not null unique,                 -- 토스 customerKey(무작위 · 22자 이상)
  billing_key  text,
  card_label   text,
  updated_at   timestamptz not null default now()
);

alter table app.payments add column if not exists payment_key text;
alter table app.payments add column if not exists renew_fails int not null default 0;

alter table app.pay_orders enable row level security;
alter table app.billing_cards enable row level security;
