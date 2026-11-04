"use client";

import { SkDetail } from "@/components/skeleton";
import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import {
  fetchCalc,
  fetchItem,
  isOnbid,
  type Calc,
  type ItemDetail,
  type OnbidDetail,
} from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { loadProfile } from "@/lib/profile";

const t = copy.report;

// 한 장 보고서(18): 상세·계산을 A4 한 장에 모음. 브라우저 인쇄로 PDF 저장.
function Report() {
  const id = decodeURIComponent(String(useParams().id));
  const bid = Number(useSearchParams().get("bid")) || null;
  const [d, setD] = useState<ItemDetail | OnbidDetail | null>(null);
  const [calc, setCalc] = useState<Calc | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const p = loadProfile();
    fetchItem(id)
      .then((x) => setD(x as ItemDetail | OnbidDetail))
      .catch(() => setFailed(true));
    fetchCalc(id, { bid, homes: p?.homes ?? 0, first: Boolean(p?.firstTime) })
      .then(setCalc)
      .catch(() => setCalc(null));
  }, [id, bid]);

  if (failed) return <LoadError onRetry={() => window.location.reload()} />;
  if (!d)
    return (
      <main className="page">
        <SkDetail />
      </main>
    );
  const ob = isOnbid(d);
  const s = calc?.selected;
  const when = ob
    ? d.bid_end
      ? `${t.closes} ${d.bid_end.slice(0, 10)} · ${dday(d.d_day)}`
      : t.undecided
    : `${t.saleDate} ${d.sale_date ?? "-"} · ${dday(d.d_day)}`;
  const market = ob
    ? d.market?.price_krw
    : (d.questions.find((q) => q.key === "worth")?.body?.market?.price_krw as number | undefined);
  const nums: [string, string][] = [
    [t.appraisal, won(d.appraisal_krw)],
    [t.min, `${won(d.min_price_krw)}${d.min_rate != null ? ` (${d.min_rate}%)` : ""}`],
    [t.failed, `${d.failed_count ?? 0}${t.times}`],
    [t.deposit, won(d.deposit_krw)],
    [t.market, market ? won(market) : t.none],
  ];
  const answers: [string, string][] = ob
    ? [
        [copy.onbid.q.buy, [d.kind_name, d.usage].filter(Boolean).join(" · ")],
        [copy.onbid.q.hold, copy.onbid.holdAnswer],
        [
          copy.onbid.q.worth,
          d.expected
            .filter((e) => e.price_krw)
            .map((e) => `${e.bucket} ${won(e.price_krw)}`)
            .join(" · ") || t.none,
        ],
        [copy.onbid.q.check, copy.onbid.checkAnswer(d.check_left)],
      ]
    : d.questions.map((q) => [q.title, q.answer]);
  const risks: string[] = ob
    ? d.warnings.filter((w) => w !== d.fatal)
    : (d.failure_table ?? [])
        .filter((r) => r.state === "걸림" || r.state === "확인 필요")
        .map((r) => `${r.state === "걸림" ? "●" : "○"} ${r.title} — ${r.why}`);
  const todo: string[] = ob
    ? d.checklist.filter((c) => c.state !== "해당 없음").map((c) => `${c.label}: ${c.what}`)
    : [];
  const cash: [string, number][] = s
    ? [
        [t.bid, s.bid_krw],
        [t.loan, -s.loan_krw],
        [t.tax, s.tax.tax_krw + s.registration_krw],
        [t.moveRepair, s.move_out_krw + s.repair_krw],
        ...(s.assumed_krw ? ([[t.assumed, s.assumed_krw]] as [string, number][]) : []),
      ]
    : [];

  return (
    <main className="page report-page">
      <div className="no-print">
        <PageHeader title={t.title} back={`/item/${encodeURIComponent(id)}`} />
        <div className="d-flex gap-8 mt-0 mb-12 mx-0">
          <button className="btn primary f-1" onClick={() => window.print()}>
            {t.print}
          </button>
        </div>
        <p className="sub fs-sm">{t.printHint}</p>
      </div>

      <article className="report">
        <header className="report-head">
          <div>
            <b>{t.brand}</b> · {ob ? `${t.onbid} ${d.case_no}` : `${d.court} ${d.case_no}`}
          </div>
          <div>{t.basis((d.computed_at ?? "").slice(0, 10))}</div>
        </header>
        <h1 className="report-title">
          {d.place} {(ob ? null : d.building) ?? d.usage ?? ""}
        </h1>
        <div className="report-sub">
          {d.address ?? ""} {d.area_m2 ? `· ${Math.round(d.area_m2 * 100) / 100}㎡` : ""} · {when}
        </div>

        <div className="report-nums">
          {nums.map(([k, v]) => (
            <div key={k}>
              <span>{k}</span>
              <b>{v}</b>
            </div>
          ))}
        </div>

        {d.fatal && <div className="report-fatal">{d.fatal}</div>}
        <p className="report-verdict">{d.verdict}</p>

        <h2>{t.answers}</h2>
        <table className="report-table">
          <tbody>
            {answers.map(([k, v]) => (
              <tr key={k}>
                <th>{k}</th>
                <td>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="report-two">
          <section>
            <h2>{t.risks}</h2>
            {risks.length ? (
              <ul>
                {risks.slice(0, 8).map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            ) : (
              <p>{t.noRisk}</p>
            )}
            {todo.length > 0 && (
              <>
                <h2>{t.todo}</h2>
                <ul>
                  {todo.map((r) => (
                    <li key={r}>□ {r}</li>
                  ))}
                </ul>
              </>
            )}
          </section>
          <section>
            <h2>{t.cash}</h2>
            {s ? (
              <table className="report-table">
                <tbody>
                  {cash.map(([k, v]) => (
                    <tr key={k}>
                      <th>{k}</th>
                      <td className="ta-right">{v < 0 ? `− ${won(-v)}` : won(v)}</td>
                    </tr>
                  ))}
                  <tr className="report-sum">
                    <th>{t.cashTotal}</th>
                    <td className="ta-right">{won(s.cash_krw)}</td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <p>{t.none}</p>
            )}
            {calc?.cap_krw != null && <p className="report-note">{t.cap(won(calc.cap_krw))}</p>}
            {s && <p className="report-note">{t.loanWho(s.loan.who, s.loan.pct)}</p>}
          </section>
        </div>

        <footer className="report-foot">{ob ? t.footOnbid : t.footCourt}</footer>
      </article>
    </main>
  );
}

export default function ReportPage() {
  return (
    <Suspense>
      <Report />
    </Suspense>
  );
}
