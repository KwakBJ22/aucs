"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { NeedLogin } from "@/components/need-login";
import { meApi, type Billing, type Payment } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.billing;
const krw = (n: number) => `${n.toLocaleString("ko-KR")}원`;
const day = (s: string) => s.slice(0, 10);
const daysLeft = (s: string) => Math.ceil((Date.parse(s) - Date.now()) / 864e5);

// 이용권·결제(11/3): 지금 이용권 → 결제 내역(누르면 상세·영수증·환불) → 환불 규칙
export default function BillingPage() {
  const { session, ready } = useSession();
  const [d, setD] = useState<Billing | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [ask, setAsk] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const token = session?.access_token ?? "";
  const load = useCallback(() => {
    if (token)
      meApi
        .billing(token)
        .then(setD)
        .catch(() => setMsg(t.fail));
  }, [token]);
  useEffect(load, [load]);
  if (!ready) return null;
  if (!session) return <NeedLogin title={t.title} />;

  const done = (m: string) => {
    setMsg(m);
    setAsk(null);
    load();
  };
  const renewing = d?.payments.find((p) => p.auto_renew && p.status === "paid");

  return (
    <main className="page">
      <PageHeader title={t.title} back="/more" />
      <section className="section">
        <h2>{t.now}</h2>
        {d && d.current.length === 0 && (
          <>
            <p className="sub mt-8">{t.free}</p>
            <Link href="/plans" className="btn soft mt-12">
              {t.toPlans}
            </Link>
          </>
        )}
        {d?.current.map((c) => (
          <div key={`${c.plan}-${c.until}-${c.period}`} className="mt-12">
            <div className="fs-lg fw-7">
              {t.planName[c.plan] ?? c.plan}{" "}
              <span className="chip gray">{t.periodName[c.period]}</span>
            </div>
            <div className="sub mt-4">
              {t.until(day(c.until))} · {t.left(daysLeft(c.until))}
            </div>
          </div>
        ))}
        {renewing && (
          <div className="mt-12">
            <div className="sub">{t.renew(day(renewing.valid_to), krw(renewing.amount_krw))}</div>
            <button
              className="btn secondary mt-8"
              onClick={() =>
                meApi
                  .stopRenew(token, renewing.payment_id)
                  .then(() => done(t.stopped))
                  .catch(() => setMsg(t.fail))
              }
            >
              {t.stopRenew}
            </button>
          </div>
        )}
        {msg && <p className="note blue mt-12">{msg}</p>}
      </section>

      <section className="section">
        <h2>{t.history}</h2>
        {d && d.payments.length + d.grants.length === 0 && (
          <p className="sub mt-8">{t.historyEmpty}</p>
        )}
        {d?.payments.map((p) => (
          <PayRow
            key={p.payment_id}
            p={p}
            open={open === p.payment_id}
            onOpen={() => setOpen(open === p.payment_id ? null : p.payment_id)}
            asking={ask === p.payment_id}
            onAsk={(v) => setAsk(v ? p.payment_id : null)}
            onRefund={() =>
              meApi
                .refund(token, p.payment_id)
                .then((r) => done(r.stopped ? t.stopped : t.refundSent))
                .catch(() => setMsg(t.fail))
            }
          />
        ))}
        {d?.grants.map((g) => (
          <div key={g.created_at} className="menu-row">
            <span>
              {t.planName[g.plan] ?? g.plan} · {t.granted}
              <span className="d-block sub">{g.reason}</span>
            </span>
            <span className="sub">{t.until(day(g.until_date))}</span>
          </div>
        ))}
      </section>

      <section className="section">
        <h2>{t.rulesTitle}</h2>
        <ul className="pl-18 sub">
          {copy.plans.refund.map((x) => (
            <li key={x} className="mt-4">
              {x}
            </li>
          ))}
          <li className="mt-4">{copy.plans.usedNote}</li>
        </ul>
      </section>
    </main>
  );
}

function PayRow(props: {
  p: Payment;
  open: boolean;
  onOpen: () => void;
  asking: boolean;
  onAsk: (v: boolean) => void;
  onRefund: () => void;
}) {
  const { p } = props;
  const state = p.refund_status === "waiting" ? t.refundWaiting : t.status[p.status];
  return (
    <div>
      <button className="menu-row w-full b-0 bg-none ta-left" onClick={props.onOpen}>
        <span>
          {t.planName[p.plan] ?? p.plan} · {t.periodName[p.period]}
          <span className="d-block sub">
            {day(p.paid_at)} · {state}
          </span>
        </span>
        <span className="num fw-6">{krw(p.amount_krw)}</span>
      </button>
      {props.open && (
        <div className="note blue mt-8">
          <div>
            {t.until(day(p.valid_to))}
            {p.refunded_krw > 0 && ` · ${t.status.refunded} ${krw(p.refunded_krw)}`}
          </div>
          {p.method_note && (
            <div>
              {t.method} · {p.method_note}
            </div>
          )}
          {p.order_id && (
            <div>
              {t.order} · {p.order_id}
            </div>
          )}
          {p.receipt_url && (
            <a href={p.receipt_url} target="_blank" rel="noreferrer">
              {t.receipt} ›
            </a>
          )}
          {p.refund && (
            <div className="mt-8">
              <div>
                {props.asking
                  ? t.refundAsk(krw(p.refund.amount_krw))
                  : `${p.refund.amount_krw > 0 ? t.refundNow(krw(p.refund.amount_krw)) : ""} · ${p.refund.rule}`}
              </div>
              {p.refund.amount_krw > 0 &&
                (props.asking ? (
                  <div className="btn-pair mt-8">
                    <button className="btn primary" onClick={props.onRefund}>
                      {t.refundGo}
                    </button>
                    <button className="btn secondary" onClick={() => props.onAsk(false)}>
                      {copy.admin.cancel}
                    </button>
                  </div>
                ) : (
                  <button className="btn secondary mt-8" onClick={() => props.onAsk(true)}>
                    {t.refundGo}
                  </button>
                ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
