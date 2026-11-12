"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { fetchPrices, type Prices } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";

const t = copy.plans;
const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

// 이용권 고르기(PAY-01). 금액·개수는 임시값(결정 #4). 결제는 사업자등록·토스페이먼츠 계약 뒤 열림.
export default function Plans() {
  const [yearly, setYearly] = useState(false);
  const [pick, setPick] = useState<string>("personal");
  // 가격은 기준표(관리자 「이용권·포인트」)에서 — 받기 전에는 문구의 값(같은 값)으로 그림(11/12)
  const [pr, setPr] = useState<Prices | null>(null);
  useEffect(() => {
    fetchPrices()
      .then(setPr)
      .catch(() => setPr(null));
  }, []);
  const month = (k: string, fb: string) => {
    const v = pr?.[k]?.month ?? pr?.[k]?.one;
    return v ? won(v) : fb;
  };
  const year = (k: string, fb: string) => {
    const v = pr?.[k]?.year;
    return v ? won(v) : fb;
  };
  const p0 = pr?.personal;
  const pct = p0?.month && p0.year ? Math.round((1 - p0.year / (p0.month * 12)) * 100) : 28;
  return (
    <main className="page">
      <PageHeader title={t.title} back="/more" />
      <div className="seg" role="tablist" style={{ maxWidth: 420 }}>
        <button
          role="tab"
          aria-selected={!yearly}
          className={!yearly ? "on" : ""}
          onClick={() => setYearly(false)}
        >
          {t.monthly}
        </button>
        <button
          role="tab"
          aria-selected={yearly}
          className={yearly ? "on" : ""}
          onClick={() => setYearly(true)}
        >
          {t.yearly(pct)}
        </button>
      </div>
      <div className="pc-grid g-3 mt-12">
        {t.list
          .filter((p) => !("hidden" in p && p.hidden))
          .map((p) => (
            <section
              key={p.key}
              className="section mt-0"
              style={{ outline: pick === p.key ? "2px solid var(--blue)" : undefined }}
              onClick={() => setPick(p.key)}
            >
              <div className="d-flex jc-between ai-baseline">
                <h2>{p.name}</h2>
                {p.tag && <span className="chip green">{p.tag}</span>}
              </div>
              <div className="fs-3xl fw-7 mt-4">
                {yearly && p.yearly ? year(p.key, p.yearly) : month(p.key, p.price)}
                <span className="sub fs-md fw-4"> {yearly && p.yearly ? t.perYear : p.per}</span>
              </div>
              <div className="sub">{p.what}</div>
              {p.items.map((x) => (
                <div key={x} className="line-row fs-md">
                  <span>{x}</span>
                  <b className="c-green">✓</b>
                </div>
              ))}
              {p.key === "one" ? (
                <Link href="/find" className="btn secondary md mt-12">
                  {t.toFind}
                </Link>
              ) : p.key !== "free" ? (
                <>
                  <button className="btn primary md mt-12" disabled title={t.payLater}>
                    {p.cta}
                  </button>
                  {/* 눌러도 반응이 없던 것(11/1) — 왜 안 되는지 바로 아래에 */}
                  <div className="sub fs-xs mt-4 ta-center">{t.payNote}</div>
                </>
              ) : null}
            </section>
          ))}
      </div>
      <Link href="/points" className="menu-row section">
        <span>
          <b>{copy.points.title}</b>
          <span className="sub d-block">{copy.points.use}</span>
        </span>
      </Link>
      <section className="section">
        <h2>{t.refundTitle}</h2>
        {t.refund.map((x) => (
          <div key={x} className="sub py-4 px-0">
            {x}
          </div>
        ))}
        <div className="sub py-4 px-0">{t.usedNote}</div>
        <div className="sub mt-8 fw-6">{t.payLater}</div>
      </section>
    </main>
  );
}
