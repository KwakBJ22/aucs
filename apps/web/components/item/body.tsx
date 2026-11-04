"use client";

import { copy } from "@/lib/copy.ko";
import { CalcBox, Row } from "@/components/calc-box";
import type { ItemDetail, Question } from "@/lib/api/items";
import { won } from "@/lib/format";
import { BuildingRows, ComplexBlock } from "@/components/item/building";
import { CheckBody } from "@/components/item/checklist";
import { FailMobile } from "@/components/item/failure";
import { RegistryBox, HoldDocLink } from "@/components/item/registry";
import { t } from "@/components/item/shared";

export function Body({ q, d }: { q: Question; d: ItemDetail }) {
  const b = q.body;
  if (q.key === "buy")
    return (
      <>
        <Row label="주소" value={b.address ?? "-"} />
        {b.area_m2 && (
          <Row
            label="면적"
            value={`${b.area_m2.toFixed(1)}㎡ (${Math.round(b.area_m2 / 3.3058)}평)`}
          />
        )}
        {b.is_share && <Row label="" value={<b className="c-red">{t.share}</b>} />}
        {b.building && <BuildingRows g={b.building} />}
        {b.redev && (
          <Row
            label={t.redev}
            value={[b.redev.name, b.redev.biz_type, b.redev.stage].filter(Boolean).join(" · ")}
          />
        )}
        {b.note && (
          <p className="sub" style={{ whiteSpace: "pre-wrap" }}>
            {b.note}
          </p>
        )}
      </>
    );
  if (q.key === "hold")
    return (
      <>
        {b.tenants.length === 0 && <p className="sub">{t.tenantsNone}</p>}
        {b.tenants.map((x: Record<string, string | number | null>, i: number) => (
          <div key={i} className="py-6 px-0 fs-md">
            <b>{x.name ?? "임차인"}</b> {x.part ?? ""}
            <div className="sub m-0">
              {[
                x.move_in && `${t.moveIn} ${x.move_in}`,
                x.fixed && `${t.fixed} ${x.fixed}`,
                x.claim && `${t.claim} ${x.claim}`,
                x.deposit_krw && `보증금 ${won(Number(x.deposit_krw))}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </div>
          </div>
        ))}
        <HoldDocLink />
        {d.failure_table ? (
          <FailMobile rows={d.failure_table} />
        ) : (
          d.failure_types.length > 0 && (
            <div className="sub mt-8">
              {t.failureTypes}: {d.failure_types.map((x) => x.title).join(" · ")}
            </div>
          )
        )}
        {d.failure_table && (
          <div className="pc-only mt-12">
            <div className="fw-6 fs-md mb-4">{t.failureTable}</div>
            <table className="w-full fs-sm" style={{ borderCollapse: "collapse" }}>
              <tbody>
                {d.failure_table.map((r) => (
                  <tr key={r.code} style={{}}>
                    <td className="py-4 px-6 nowrap" style={{ opacity: 0.6 }}>
                      {r.code}
                    </td>
                    <td className="py-4 px-6">{r.title}</td>
                    <td
                      className="py-4 px-6 nowrap"
                      style={{
                        fontWeight: r.state === "걸림" || r.state === "확인 필요" ? 600 : 400,
                        color: t.failColor[r.state],
                      }}
                    >
                      {r.state}
                    </td>
                    <td className="sub py-4 px-6">{r.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="sub mt-4">{t.failureTableNote}</div>
          </div>
        )}
        {b.signals
          .filter((s: { status: string }) => s.status !== "모름")
          .map((s: { rule_id: string; title: string; level: string }) => (
            <div
              key={s.rule_id}
              className="fs-md py-6 px-0"
              style={{ color: s.level === "fatal" ? "var(--red)" : "var(--amber)" }}
            >
              ◆ {s.title}
            </div>
          ))}
        {!d.outcome?.closed && <RegistryBox />}
      </>
    );
  if (q.key === "worth")
    return (
      <>
        {d.court_bidders?.avg != null && (
          <Row
            label={copy.me.courtBidders}
            value={copy.me.courtBiddersValue(d.court_bidders.avg, d.court_bidders.n)}
          />
        )}
        {b.range_krw && (
          <>
            <Row
              label={t.rangeLabel}
              value={
                <b>
                  {won(b.range_krw[0]) === won(b.range_krw[1])
                    ? won(b.range_krw[0])
                    : `${won(b.range_krw[0])} ~ ${won(b.range_krw[1])}`}
                </b>
              }
            />
            {b.assume_risk && (
              <p className="fs-sm c-amber mb-0">
                {copy.item.calc.assumeTitle} · {copy.item.calc.assumeNeed}
              </p>
            )}
            <p className="sub">{t.sample(b.rate.n)}</p>
            {b.market && (
              <>
                <Row label={t.market(b.market.n)} value={<b>{won(b.market.price_krw)}</b>} />
                <div className="sub m-0 fs-xs">
                  {t.recentTrades}{" "}
                  {b.market.recent
                    .slice(0, 3)
                    .map(
                      (x: { date: string; floor: number | null; price_krw: number }) =>
                        `${x.date.slice(2, 7).replace("-", ".")} ${x.floor ?? "-"}층 ${won(x.price_krw)}`,
                    )
                    .join(" · ")}
                </div>
              </>
            )}
            {b.notes.map((n: string) => (
              <div key={n} className="fs-md c-amber py-2 px-0">
                ◆ {n}
              </div>
            ))}
          </>
        )}
        {b.complex && <ComplexBlock cx={b.complex} />}
      </>
    );
  if (q.key === "cost")
    return (
      <>
        <Row label={t.deposit} value={<b>{won(b.deposit_krw)}</b>} />
        <p className="fs-md mt-8 mb-4 mx-0">{b.schedule_line}</p>
        <div className="sub mt-8 mb-2 mx-0">{t.deadlines}</div>
        {b.deadlines.map((x: { key: string; label: string; short: string }) => (
          <Row key={x.key} label={x.label} value={x.short} />
        ))}
        {!d.outcome?.closed && <CalcBox id={d.item_id} />}
      </>
    );
  return <CheckBody b={b} />;
}
