"use client";

import type { PayOrder } from "@/lib/api/me";

// 토스페이먼츠 결제창 부르기(11/23 미리 구성). 결제 계약 뒤 테스트 키로 수단마다 한 번씩 눌러 확인할 것.
// SDK v2 결제창(payment): https://docs.tosspayments.com/sdk/v2/js/payment
// 카드 결제 값은 공식 문서 예제로 확인함(11/23). 계좌이체 · 입금 전용 계좌 · 간편결제 값은 문서에서 확인하지 못했음 — 테스트 때 확인.
type TossPayment = {
  requestPayment: (o: Record<string, unknown>) => Promise<void>;
  requestBillingAuth: (o: Record<string, unknown>) => Promise<void>;
};
type TossFn = (clientKey: string) => { payment: (o: { customerKey: string }) => TossPayment };
declare global {
  interface Window {
    TossPayments?: TossFn;
  }
}

const SRC = "https://js.tosspayments.com/v2/standard";
let loading: Promise<TossFn> | null = null;

function load(): Promise<TossFn> {
  if (window.TossPayments) return Promise.resolve(window.TossPayments);
  loading ??= new Promise<TossFn>((ok, no) => {
    const s = document.createElement("script");
    s.src = SRC;
    s.async = true;
    s.onload = () => (window.TossPayments ? ok(window.TossPayments) : no(new Error("load")));
    s.onerror = () => {
      loading = null;
      no(new Error("load"));
    };
    document.head.appendChild(s);
  });
  return loading;
}

// 화면 수단(copy.checkout.methods 의 열쇠) → 결제창 값
const METHOD: Record<string, Record<string, unknown>> = {
  card: { method: "CARD", card: { flowMode: "DEFAULT" } },
  bank: { method: "TRANSFER" },
  vbank: { method: "VIRTUAL_ACCOUNT" },
  toss: { method: "CARD", card: { flowMode: "DIRECT", easyPay: "TOSSPAY" } },
  naver: { method: "CARD", card: { flowMode: "DIRECT", easyPay: "NAVERPAY" } },
  kakao: { method: "CARD", card: { flowMode: "DIRECT", easyPay: "KAKAOPAY" } },
};

/** 한 번 결제(1년 · 한 건). 끝나면 토스가 /checkout/done 또는 /checkout/fail 로 돌려보냄. */
export async function openPayment(o: PayOrder, method: string): Promise<void> {
  const T = await load();
  const origin = window.location.origin;
  await T(o.client_key)
    .payment({ customerKey: o.customer_key })
    .requestPayment({
      ...(METHOD[method] ?? METHOD.card),
      amount: { currency: "KRW", value: o.amount_krw },
      orderId: o.order_id,
      orderName: o.order_name,
      successUrl: `${origin}/checkout/done`,
      failUrl: `${origin}/checkout/fail`,
      ...(o.email ? { customerEmail: o.email } : {}),
    });
}

/** 매달: 카드 등록 창. 끝나면 /checkout/done?authKey=…&customerKey=… 로 돌아옴 → 서버가 첫 달 결제. */
export async function openCardAuth(clientKey: string, customerKey: string): Promise<void> {
  const T = await load();
  const origin = window.location.origin;
  await T(clientKey)
    .payment({ customerKey })
    .requestBillingAuth({
      method: "CARD",
      successUrl: `${origin}/checkout/done`,
      failUrl: `${origin}/checkout/fail`,
    });
}

// 입금 전용 계좌 은행(금융결제원 은행 코드 두 자리 — 기억으로 적은 표, 테스트 때 한 번 확인). 없는 코드는 숫자 그대로.
export const BANKS: Record<string, string> = {
  "02": "산업",
  "03": "기업",
  "04": "국민",
  "07": "수협",
  "11": "농협",
  "20": "우리",
  "23": "SC제일",
  "31": "아이엠뱅크",
  "32": "부산",
  "34": "광주",
  "35": "제주",
  "37": "전북",
  "39": "경남",
  "45": "새마을금고",
  "48": "신협",
  "71": "우체국",
  "81": "하나",
  "88": "신한",
  "89": "케이뱅크",
  "90": "카카오뱅크",
  "92": "토스뱅크",
};
