"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { NeedLogin } from "@/components/need-login";
import { payApi, type PayResult } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { BANKS } from "@/lib/pay";

const t = copy.checkout;
const D = t.done;
const wonFull = (n: number) => `${n.toLocaleString("ko-KR")}원`;

// 결제 뒤(11/23 미리 구성): 토스가 돌려보낸 곳.
//  · 한 번 결제: ?paymentKey&orderId&amount → 서버가 금액을 주문과 맞춰 보고 승인 → 이용권
//  · 매달 카드 등록: ?authKey&customerKey → 서버가 카드 등록 + 첫 달 결제
// 새로 고침 · 뒤로 가기로 다시 와도 서버가 한 번만 처리함(주문에 결제가 이미 있으면 그 결과를 돌려줌).
function Done() {
  const sp = useSearchParams();
  const { session, ready } = useSession();
  const [r, setR] = useState<PayResult | null>(null);
  const [err, setErr] = useState("");
  const sent = useRef(false);

  useEffect(() => {
    if (!session || sent.current) return;
    sent.current = true;
    const tk = session.access_token;
    const pk = sp.get("paymentKey");
    const oid = sp.get("orderId");
    const amt = Number(sp.get("amount"));
    const ak = sp.get("authKey");
    const ck = sp.get("customerKey");
    const job =
      pk && oid && amt
        ? payApi.confirm(tk, { payment_key: pk, order_id: oid, amount: amt })
        : ak && ck
          ? payApi.cardIssue(tk, { auth_key: ak, customer_key: ck })
          : Promise.reject(new Error(D.noParams));
    job.then(setR).catch((e: Error) => setErr(e.message));
  }, [session, sp]);

  if (!ready) return <main className="page narrow" />;
  if (!session) return <NeedLogin title={t.title} />;

  const go = r?.item_id ? (
    <Link href={`/item/${encodeURIComponent(r.item_id)}`} className="btn primary mt-12">
      {D.toItem}
    </Link>
  ) : (
    <Link href="/find" className="btn primary mt-12">
      {D.toHome}
    </Link>
  );

  return (
    <main className="page narrow checkout">
      <PageHeader title={t.title} />
      <section className="section ta-center py-32 px-18">
        {!r && !err && <p className="sub m-0">{D.checking}</p>}
        {err && (
          <>
            <h2 className="co-title">{D.failTitle}</h2>
            <p className="sub">{err}</p>
            <Link href="/plans" className="btn primary mt-12">
              {D.again}
            </Link>
            <Link href="/more" className="link d-block mt-12">
              {D.ask}
            </Link>
          </>
        )}
        {r?.status === "card" && (
          <>
            <h2 className="co-title">{D.card}</h2>
            {r.card && <p className="sub">{t.cardSaved(r.card)}</p>}
          </>
        )}
        {r?.status === "paid" && (
          <>
            <h2 className="co-title">✓ {D.paid}</h2>
            <p className="sub m-0">{r.order_name}</p>
            <p className="m-0 mt-8">
              <b>{wonFull(r.amount_krw ?? 0)}</b>
              {r.until ? ` · ${t.until(r.until)}` : ""}
            </p>
            {r.card && <p className="sub">{t.cardSaved(r.card)}</p>}
            {go}
            {r.receipt_url && (
              <a
                href={r.receipt_url}
                target="_blank"
                rel="noreferrer"
                className="link d-block mt-12"
              >
                {D.receipt}
              </a>
            )}
          </>
        )}
        {r?.status === "waiting" && (
          <>
            <h2 className="co-title">{D.waiting}</h2>
            <p className="sub">{D.waitingSub}</p>
            <div className="ta-left mt-12">
              <div className="line-row co-row">
                <span className="sub">{D.bank}</span>
                <b>{BANKS[r.vbank?.bank ?? ""] ?? r.vbank?.bank ?? "-"}</b>
              </div>
              <div className="line-row co-row">
                <span className="sub">{D.account}</span>
                <b>{r.vbank?.account ?? "-"}</b>
              </div>
              <div className="line-row co-row">
                <span className="sub">{D.due}</span>
                <b>{r.vbank?.due?.slice(0, 16).replace("T", " ") ?? "-"}</b>
              </div>
              <div className="line-row co-total">
                <b>{t.amount}</b>
                <b className="co-price">{wonFull(r.amount_krw ?? 0)}</b>
              </div>
            </div>
          </>
        )}
        {r && !["paid", "waiting", "card"].includes(r.status) && (
          <>
            <h2 className="co-title">{D.failTitle}</h2>
            {r.fail && <p className="sub">{r.fail}</p>}
            <Link href="/plans" className="btn primary mt-12">
              {D.again}
            </Link>
          </>
        )}
        {r && (
          <Link href="/more/billing" className="link d-block mt-12">
            {D.history}
          </Link>
        )}
      </section>
    </main>
  );
}

export default function CheckoutDonePage() {
  return (
    <Suspense>
      <Done />
    </Suspense>
  );
}
