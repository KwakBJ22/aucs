"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { NeedLogin } from "@/components/need-login";
import { fetchItem, fetchPrices, type ItemDetail, type Prices } from "@/lib/api/items";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.checkout;
const P = copy.plans;
const wonFull = (n: number) => `${n.toLocaleString("ko-KR")}원`;
const DAYS = "일월화수목금토";

// 결제(11/22 디자인 · 11/22 대표님 「미리 만들어 두고 결제가 열리면 붙이기만」).
// /checkout?plan=personal(&y=1) · /checkout?plan=one&item=물건ID
// 지금은 결제 계약 전이라 마지막 단추만 잠가 둠 — 토스페이먼츠가 열리면 pay() 안에 결제창 부르기만 넣으면 됨.
function Checkout() {
  const sp = useSearchParams();
  const plan = sp.get("plan") === "one" ? "one" : "personal";
  const yearly = plan === "personal" && sp.get("y") === "1";
  const itemId = sp.get("item");
  const { session, ready } = useSession();
  const [pr, setPr] = useState<Prices | null>(null);
  const [item, setItem] = useState<ItemDetail | null>(null);
  const [method, setMethod] = useState<string>("toss");

  useEffect(() => {
    fetchPrices()
      .then(setPr)
      .catch(() => setPr(null));
  }, []);
  useEffect(() => {
    if (!itemId || !session) return;
    fetchItem(itemId)
      .then(setItem)
      .catch(() => setItem(null));
  }, [itemId, session]);

  if (!ready) return <main className="page narrow" />;
  if (!session) return <NeedLogin title={t.title} />;

  const p = P.list.find((x) => x.key === plan)!;
  // 값은 기준표(관리자 「이용권·포인트」) — 받기 전에는 문구의 값
  const amount =
    plan === "one"
      ? (pr?.one?.one ?? pr?.one?.month ?? null)
      : yearly
        ? (pr?.personal?.year ?? null)
        : (pr?.personal?.month ?? null);
  const price = amount != null ? wonFull(amount) : yearly ? p.yearly : p.price;

  // 한 건: 매각기일 다음 날까지
  let until: string | null = null;
  if (plan === "one" && item?.sale_date) {
    const d = new Date(`${item.sale_date}T00:00:00+09:00`);
    d.setDate(d.getDate() + 1);
    until = t.untilOne(d.getMonth() + 1, d.getDate(), DAYS[d.getDay()] ?? "");
  }
  const rows: [string, string][] = [
    [t.period, plan === "one" ? (until ?? t.periodOne) : yearly ? t.periodYear : t.periodMonth],
    [t.includes, plan === "one" ? t.includesOne : p.what],
  ];

  // 결제 붙일 자리: 결제가 열리면 여기서 토스페이먼츠 결제창을 부름(method · plan · yearly · itemId)
  const open = false;
  const pay = () => undefined;

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
            ? item
              ? `${item.court} ${item.case_no} · ${item.building ?? item.place}`
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
          {t.methods.map(([k, label]) => (
            <button
              key={k}
              role="radio"
              aria-checked={method === k}
              className={method === k ? "on" : ""}
              onClick={() => setMethod(k)}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="sub mt-12 mb-0">{t.methodNote}</p>
      </section>
      <p className="sub co-refund">{plan === "one" ? t.refundOne : t.refundPlan}</p>
      <button className="btn primary" disabled={!open} onClick={pay}>
        {t.pay(price)}
      </button>
      {!open && <p className="sub ta-center mt-8">{P.payLater}</p>}
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
