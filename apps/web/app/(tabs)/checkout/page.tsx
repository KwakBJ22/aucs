"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { NeedLogin } from "@/components/need-login";
import { fetchPrices, type Prices } from "@/lib/api/items";
import { payApi, type PayQuote } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { openCardAuth, openPayment } from "@/lib/pay";

const t = copy.checkout;
const P = copy.plans;
const wonFull = (n: number) => `${n.toLocaleString("ko-KR")}원`;
const DAYS = "일월화수목금토";

// 결제(11/22 디자인 · 11/22 대표님 「미리 만들어 두고 결제가 열리면 붙이기만」).
// /checkout?plan=personal(&y=1) · /checkout?plan=one&item=물건ID
// 11/23: 결제 전 · 후를 붙여 둠 — 서버에 토스페이먼츠 키가 들어가면(quote.open) 단추가 열림.
// 1년 · 한 건 = 주문(서버가 금액) → 결제창 → /checkout/done · 매달 = 카드 등록 → /checkout/done 에서 첫 달 결제.
function Checkout() {
  const sp = useSearchParams();
  const plan = sp.get("plan") === "one" ? "one" : "personal";
  const yearly = plan === "personal" && sp.get("y") === "1";
  const itemId = sp.get("item");
  const { session, ready } = useSession();
  const [pr, setPr] = useState<Prices | null>(null);
  const [q, setQ] = useState<PayQuote | null>(null);
  const [method, setMethod] = useState<string>("toss");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const period = plan === "one" ? "one" : yearly ? "year" : "month";

  useEffect(() => {
    fetchPrices()
      .then(setPr)
      .catch(() => setPr(null));
  }, []);
  // 값 · 기간 · 결제가 열렸는지 · 한 건 물건 이름(상세가 잠겨 있어도) — 서버가 정한 값
  useEffect(() => {
    if (!session) return;
    payApi
      .quote(session.access_token, plan, period, itemId)
      .then(setQ)
      .catch((e: Error) => setErr(e.message));
  }, [session, plan, period, itemId]);

  if (!ready) return <main className="page narrow" />;
  if (!session) return <NeedLogin title={t.title} />;

  const p = P.list.find((x) => x.key === plan)!;
  // 값은 기준표(관리자 「이용권·포인트」) — 받기 전에는 문구의 값
  const amount =
    q?.amount_krw ??
    (plan === "one"
      ? (pr?.one?.one ?? pr?.one?.month ?? null)
      : yearly
        ? (pr?.personal?.year ?? null)
        : (pr?.personal?.month ?? null));
  const price = amount != null ? wonFull(amount) : yearly ? p.yearly : p.price;

  // 한 건: 매각기일 다음 날까지(서버 quote.until)
  let until: string | null = null;
  if (plan === "one" && q?.until) {
    const d = new Date(`${q.until}T00:00:00+09:00`);
    until = t.untilOne(d.getMonth() + 1, d.getDate(), DAYS[d.getDay()] ?? "");
  }
  const monthly = period === "month";
  const rows: [string, string][] = [
    [
      t.period,
      plan === "one"
        ? (until ?? t.periodOne)
        : `${yearly ? t.periodYear : t.periodMonth}${q ? ` · ${t.until(q.until)}` : ""}`,
    ],
    [t.includes, plan === "one" ? t.includesOne : p.what],
  ];

  const open = Boolean(q?.open) && (plan !== "one" || Boolean(q?.item));
  const methods = monthly ? t.methods.filter(([k]) => k === "card") : t.methods;
  const pay = async () => {
    if (!open || busy) return;
    setBusy(true);
    setErr("");
    try {
      const tk = session.access_token;
      if (monthly) {
        const c = await payApi.cardStart(tk);
        await openCardAuth(c.client_key, c.customer_key);
      } else {
        const o = await payApi.order(tk, { plan, period, item_id: itemId, method });
        await openPayment(o, method);
      }
    } catch (e) {
      // 결제창을 닫으면 SDK 가 오류를 던짐(그만둔 것) — 문장만 보여 주고 다시 누를 수 있게
      setErr(e instanceof Error && e.message !== "load" ? e.message : t.done.failTitle);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page narrow checkout">
      <Link href="/plans" className="back-link pc-only">
        ‹ {P.title}
      </Link>
      <PageHeader title={t.title} back="/plans" />
      <section className="section">
        <div className="sub m-0">{yearly ? `${p.name} · ${t.year}` : p.name}</div>
        <h2 className="co-title">
          {plan === "one"
            ? q?.item
              ? `${q.item.no} · ${q.item.address ?? ""}`
              : t.pickItem
            : yearly
              ? t.planYear
              : t.planMonth}
        </h2>
        {rows.map(([k, v]) => (
          <div key={k} className="line-row co-row">
            <span className="sub">{k}</span>
            <b>{v}</b>
          </div>
        ))}
        <div className="line-row co-total">
          <b>{t.amount}</b>
          <b className="co-price">{price}</b>
        </div>
      </section>
      <section className="section">
        <h2>{t.method}</h2>
        <div className="co-methods" role="radiogroup" aria-label={t.method}>
          {methods.map(([k, label]) => (
            <button
              key={k}
              role="radio"
              aria-checked={monthly || method === k}
              className={monthly || method === k ? "on" : ""}
              onClick={() => setMethod(k)}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="sub mt-12 mb-0">
          {monthly ? t.monthCard : t.methodNote}
          {monthly && q?.card ? ` · ${t.cardSaved(q.card)}` : ""}
        </p>
      </section>
      <p className="sub co-refund">{plan === "one" ? t.refundOne : t.refundPlan}</p>
      <button className="btn primary" disabled={!open || busy} onClick={() => void pay()}>
        {busy ? t.opening : monthly ? t.payCard(price) : t.pay(price)}
      </button>
      {err && <p className="sub c-red ta-center mt-8">{err}</p>}
      {q && !q.open && <p className="sub ta-center mt-8">{P.payLater}</p>}
    </main>
  );
}

export default function CheckoutPage() {
  return (
    <Suspense>
      <Checkout />
    </Suspense>
  );
}
