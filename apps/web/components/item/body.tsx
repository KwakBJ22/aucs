"use client";

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
        {b.is_share && <Row label="" value={<b style={{ color: "var(--red)" }}>{t.share}</b>} />}
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
          <div key={i} style={{ padding: "6px 0", fontSize: 14 }}>
            <b>{x.name ?? "임차인"}</b> {x.part ?? ""}
            <div className="sub" style={{ margin: 0 }}>
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
            <div className="sub" style={{ marginTop: 8 }}>
              {t.failureTypes}: {d.failure_types.map((x) => x.title).join(" · ")}
            </div>
          )
        )}
        {d.failure_table && (
          <div className="pc-only" style={{ marginTop: 12 }}>
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{t.failureTable}</div>
            <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
              <tbody>
                {d.failure_table.map((r) => (
                  <tr key={r.code} style={{}}>
                    <td style={{ padding: "4px 6px", whiteSpace: "nowrap", opacity: 0.6 }}>
                      {r.code}
                    </td>
                    <td style={{ padding: "4px 6px" }}>{r.title}</td>
                    <td
                      style={{
                        padding: "4px 6px",
                        whiteSpace: "nowrap",
                        fontWeight: r.state === "신호 없음" ? 400 : 600,
                        color:
                          r.state === "걸림"
                            ? "var(--red, #d33)"
                            : r.state === "확인 필요"
                              ? "var(--orange, #d80)"
                              : undefined,
                        opacity: r.state === "신호 없음" ? 0.6 : 1,
                      }}
                    >
                      {r.state}
                    </td>
                    <td className="sub" style={{ padding: "4px 6px" }}>
                      {r.why}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="sub" style={{ marginTop: 4 }}>
              {t.failureTableNote}
            </div>
          </div>
        )}
        {b.signals
          .filter((s: { status: string }) => s.status !== "모름")
          .map((s: { rule_id: string; title: string; level: string }) => (
            <div
              key={s.rule_id}
              style={{
                fontSize: 14,
                padding: "6px 0",
                color: s.level === "fatal" ? "var(--red)" : "var(--amber)",
              }}
            >
              ◆ {s.title}
            </div>
          ))}
        <RegistryBox />
      </>
    );
  if (q.key === "worth")
    return (
      <>
        {b.range_krw && (
          <>
            <Row
              label={t.rangeLabel}
              value={
                <b>
                  {won(b.range_krw[0])} ~ {won(b.range_krw[1])}
                </b>
              }
            />
            <p className="sub">{t.sample(b.rate.n)}</p>
            {b.market && (
              <>
                <Row label={t.market(b.market.n)} value={<b>{won(b.market.price_krw)}</b>} />
                <div className="sub" style={{ margin: 0, fontSize: 12 }}>
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
              <div key={n} style={{ fontSize: 14, color: "var(--amber)", padding: "2px 0" }}>
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
        <p style={{ fontSize: 14, margin: "8px 0 4px" }}>{b.schedule_line}</p>
        <div className="sub" style={{ margin: "8px 0 2px" }}>
          {t.deadlines}
        </div>
        {b.deadlines.map((x: { key: string; label: string; short: string }) => (
          <Row key={x.key} label={x.label} value={x.short} />
        ))}
        <CalcBox id={d.item_id} />
      </>
    );
  return <CheckBody b={b} />;
}
