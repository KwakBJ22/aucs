"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { NeedLogin } from "@/components/need-login";
import { Delayed, SkRows } from "@/components/skeleton";
import { meApi, payApi, type PointSummary } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { parseTime } from "@/lib/format";
import { openPayment } from "@/lib/pay";

const t = copy.points;
const CO = copy.checkout;
const wonFull = (n: number) => `${n.toLocaleString("ko-KR")}원`;
const day = (iso: string) => {
  const d = parseTime(iso);
  return `${d.getFullYear()}.${d.getMonth() + 1}.${d.getDate()}`;
};

// 포인트함(11/26 대표님): 잔액 · 충전 · 내역. 서류 올리고 포인트 받기는 뺌.
// 충전 = 결제(/me/pay/order plan=points) → 토스 결제창 → /checkout/done → 포인트 한 줄(서버가 금액을 정함)
export default function PointsPage() {
  const { session, ready } = useSession();
  const token = session?.access_token ?? "";
  const [sum, setSum] = useState<PointSummary | null>(null);
  const [krw, setKrw] = useState<number | null>(null);
  const [method, setMethod] = useState("toss");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) return;
    meApi
      .points(token)
      .then((x) => {
        setSum(x);
        setKrw((v) => v ?? x.charge?.krw?.[1] ?? x.charge?.krw?.[0] ?? null);
      })
      .catch(() => setSum(null));
  }, [token]);

  if (!ready)
    return (
      <main className="page narrow">
        <SkRows n={6} />
      </main>
    );
  if (!session) return <NeedLogin title={t.title} />;

  const open = Boolean(sum?.charge?.open) && krw != null;
  const charge = async () => {
    if (!open || busy || krw == null) return;
    setBusy(true);
    setErr("");
    try {
      const o = await payApi.order(token, {
        plan: "points",
        period: "one",
        item_id: null,
        method,
        amount_krw: krw,
      });
      await openPayment(o, method);
    } catch (e) {
      // 결제창을 닫으면 SDK 가 오류를 던짐(그만둔 것) — 문장만 보여 주고 다시 누를 수 있게
      setErr(e instanceof Error && e.message !== "load" ? e.message : CO.done.failTitle);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page narrow checkout">
      <PageHeader title={t.title} />
      <section className="section">
        <div className="d-flex jc-between ai-end gap-12">
          <div>
            <div className="sub m-0">{t.balance}</div>
            <div className="item-price pt-balance">{sum ? t.pt(sum.balance) : "-"}</div>
          </div>
          <Link href="/plans" className="link f-none">
            {t.usePlans}
          </Link>
        </div>
        <p className="sub mt-4 mb-0">{t.useLine}</p>
      </section>

      {/* 포인트 모으기(11/26 대표님): 옥스아카데미 · 잘못된 정보 알리기 — 점수는 기준표 */}
      {sum?.earn && (
        <section className="section">
          <h2>{t.earnTitle}</h2>
          {sum.earn.academy_stage ? (
            <p className="fs-md mt-8 mb-0">
              {t.earnAcademy(sum.earn.academy_stage, sum.earn.academy_stage_mid ?? 0)}{" "}
              <Link href="/academy" className="link in">
                {t.earnGo}
              </Link>
            </p>
          ) : null}
          {sum.earn.report ? <p className="fs-md mt-8 mb-0">{t.earnReport(sum.earn.report)}</p> : null}
        </section>
      )}

      <section className="section">
        <h2>{t.charge}</h2>
        <div className="sub mt-8 mb-8">{t.chargeAmount}</div>
        <div className="co-methods" role="radiogroup" aria-label={t.chargeAmount}>
          {(sum?.charge?.krw ?? []).map((n) => (
            <button
              key={n}
              role="radio"
              aria-checked={krw === n}
              className={krw === n ? "on" : ""}
              onClick={() => setKrw(n)}
            >
              {wonFull(n)}
            </button>
          ))}
        </div>
        <div className="sub mt-14 mb-8">{t.method}</div>
        <div className="co-methods" role="radiogroup" aria-label={t.method}>
          {CO.methods.map(([k, label]) => (
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
        {sum && <p className="sub mt-12 mb-0">{t.chargeNote(sum.charge?.expire_years ?? 5)}</p>}
        {sum && !sum.charge?.open && <p className="sub mt-4 mb-0">{copy.plans.payLater}</p>}
        <button
          className="btn primary mt-12 w-full"
          disabled={!open || busy}
          onClick={() => void charge()}
        >
          {busy ? t.opening : t.chargeGo(krw != null ? wonFull(krw) : "")}
        </button>
        {err && <p className="sub c-red mt-8 mb-0">{err}</p>}
      </section>

      <section className="section">
        <h2>{t.historyTitle}</h2>
        {!sum && (
          <Delayed>
            <SkRows n={4} />
          </Delayed>
        )}
        {sum?.history?.length === 0 && <p className="sub mt-12">{t.historyEmpty}</p>}
        {sum?.history?.map((h, i) => (
          <div key={i} className="line-row co-row">
            <span>
              {t.reason[h.reason] ?? h.reason}
              <span className="sub d-block m-0 fs-sm">
                {day(h.created_at)}
                {h.delta > 0 && h.expires_at ? ` · ${t.until(day(h.expires_at))}` : ""}
              </span>
            </span>
            <b className={h.delta > 0 ? "c-blue-text" : ""}>{t.sign(h.delta)}</b>
          </div>
        ))}
      </section>

      <details className="section">
        <summary className="fw-6">{t.rulesTitle}</summary>
        <ul className="sub fs-sm mt-8 mb-0 lh-16">
          {t.rules.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </details>
    </main>
  );
}
