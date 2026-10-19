"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { NeedLogin } from "@/components/need-login";
import { fetchCalc, fetchItem, type Calc, type ItemDetail } from "@/lib/api/items";
import { meApi, type Compare } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { loadProfile } from "@/lib/profile";

const t = copy.compare;
type Col = { id: string; d: ItemDetail | null; calc: Calc | null };
const REASONS = ["budget", "assumed_unclear", "field_bad", "other"] as const;

const answer = (d: ItemDetail | null, key: string) =>
  d?.questions.find((q) => q.key === key)?.answer ?? "-";

// 비교함: 같은 기준으로 3~5개 나란히. 뺄 때 이유를 남김(다음 추천에서 덜 보여 줌)
export default function ComparePage() {
  const { session, ready } = useSession();
  const token = session?.access_token ?? null;
  const [data, setData] = useState<Compare | null>(null);
  const [cols, setCols] = useState<Col[]>([]);
  const [asking, setAsking] = useState<string | null>(null);

  const load = (tok: string) =>
    meApi
      .compare(tok)
      .then(async (c) => {
        setData(c);
        const p = loadProfile();
        const homes = p?.homes ?? 0;
        const rows = await Promise.all(
          c.items.map(async (id) => {
            const [d, calc] = await Promise.all([
              fetchItem(id).catch(() => null),
              fetchCalc(id, { homes, first: Boolean(p?.firstTime) }).catch(() => null),
            ]);
            return { id, d, calc };
          }),
        );
        setCols(rows);
      })
      .catch(() => setData({ items: [], excluded: [], max: 5 }));

  useEffect(() => {
    if (token) void load(token);
  }, [token]);

  if (!ready) return null;
  if (!session || !token) return <NeedLogin title={t.title} />;

  const exclude = (id: string, reason: (typeof REASONS)[number]) => {
    setAsking(null);
    meApi
      .exclude(token, id, reason)
      .then(() => load(token))
      .catch(() => {});
  };
  const undo = (id: string) => {
    meApi
      .unexclude(token, id)
      .then(() => load(token))
      .catch(() => {});
  };

  const rows: { label: string; cell: (c: Col) => React.ReactNode }[] = [
    {
      label: t.rows.date,
      cell: (c) => (c.d ? `${dday(c.d.d_day)} · ${c.d.sale_date?.slice(5) ?? ""}` : "-"),
    },
    {
      label: t.rows.min,
      cell: (c) =>
        c.d ? (
          <>
            <b>{won(c.d.min_price_krw)}</b>
            <div className="sub">
              {copy.card.ofAppraisal} {c.d.min_rate}%
            </div>
          </>
        ) : (
          "-"
        ),
    },
    {
      label: t.rows.cash,
      cell: (c) =>
        c.calc ? (
          <>
            <b>{won(c.calc.selected.cash_krw)}</b>
            <div className="sub">{t.atBid(won(c.calc.selected.bid_krw))}</div>
          </>
        ) : (
          "-"
        ),
    },
    { label: t.rows.hold, cell: (c) => answer(c.d, "hold") },
    { label: t.rows.worth, cell: (c) => answer(c.d, "worth") },
    { label: t.rows.check, cell: (c) => answer(c.d, "check") },
  ];

  return (
    <main className="page compare-page">
      <div className="topbar">
        <div className="brand">{t.title}</div>
        {data && (
          <span className="sub">
            {cols.length}/{data.max}
          </span>
        )}
      </div>
      {data && data.items.length === 0 && (
        <section className="section">
          <p className="sub">{t.empty}</p>
          <Link href="/watch">{copy.watch.title} ›</Link>
        </section>
      )}
      {cols.length > 0 && (
        <section className="section" style={{ padding: 0, overflowX: "auto" }}>
          <table className="compare-table">
            <thead>
              <tr>
                <th />
                {cols.map((c) => (
                  <th key={c.id}>
                    <Link href={`/item/${encodeURIComponent(c.id)}`} style={{ color: "inherit" }}>
                      <div className="sub">
                        {c.d?.court} {c.d?.case_no}
                      </div>
                      <div style={{ fontWeight: 600 }}>
                        {c.d?.place} {c.d?.building ?? c.d?.usage}
                      </div>
                    </Link>
                    {c.d?.fatal && <div className="fatal">{c.d.fatal}</div>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label}>
                  <td className="sub">{r.label}</td>
                  {cols.map((c) => (
                    <td key={c.id}>{r.cell(c)}</td>
                  ))}
                </tr>
              ))}
              <tr>
                <td />
                {cols.map((c) => (
                  <td key={c.id}>
                    {asking === c.id ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <span className="sub">{t.why}</span>
                        {REASONS.map((r) => (
                          <button
                            key={r}
                            className="chip gray"
                            style={{ border: 0, minHeight: 36 }}
                            onClick={() => exclude(c.id, r)}
                          >
                            {t.reasons[r]}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <button
                        className="chip gray"
                        style={{ border: 0, minHeight: 36 }}
                        onClick={() => setAsking(c.id)}
                      >
                        {t.drop}
                      </button>
                    )}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </section>
      )}
      {cols.length > 0 && <div className="sub">{t.note}</div>}
      {data && data.excluded.length > 0 && (
        <section className="section">
          <h2>{t.excluded}</h2>
          {data.excluded.map((e) => (
            <div
              key={e.item_id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "8px 0",
                borderTop: "1px solid var(--line)",
                fontSize: 14,
              }}
            >
              <span>
                {e.place}
                <span className="sub" style={{ display: "block" }}>
                  {e.case_no} · {t.reasons[e.reason as (typeof REASONS)[number]] ?? e.reason} ·{" "}
                  {e.at}
                </span>
              </span>
              <button
                className="chip gray"
                style={{ border: 0, minHeight: 32 }}
                onClick={() => undo(e.item_id)}
              >
                {t.undo}
              </button>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
