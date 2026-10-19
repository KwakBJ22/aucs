"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { NeedLogin } from "@/components/need-login";
import { fetchCalc, fetchItem, type Calc, type ItemDetail } from "@/lib/api/items";
import { meApi, type Compare, type Workspace } from "@/lib/api/me";
import { PageHeader } from "@/components/layout/page-header";
import { useIsPc } from "@/lib/use-pc";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { loadProfile } from "@/lib/profile";

const t = copy.compare;
type Col = { id: string; d: ItemDetail | null; calc: Calc | null; w: Workspace | null };
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
  const [more, setMore] = useState(false);
  const pc = useIsPc();

  const load = (tok: string) =>
    meApi
      .compare(tok)
      .then(async (c) => {
        setData(c);
        const p = loadProfile();
        const homes = p?.homes ?? 0;
        const rows = await Promise.all(
          c.items.map(async (id) => {
            const [d, calc, w] = await Promise.all([
              fetchItem(id).catch(() => null),
              fetchCalc(id, { homes, first: Boolean(p?.firstTime) }).catch(() => null),
              meApi.workspace(tok, id).catch(() => null),
            ]);
            return { id, d, calc, w };
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

  const marketRatio = (c: Col): number | null => {
    const m = c.d?.questions.find((q) => q.key === "worth")?.body?.market?.price_krw as number | undefined;
    return m && c.d?.min_price_krw ? Math.round((c.d.min_price_krw * 100) / m) : null;
  };
  const failHit = (c: Col): number | null =>
    c.d?.failure_table ? c.d.failure_table.filter((r) => r.state !== "신호 없음").length : null;
  // 줄마다 가장 나은 값(작을수록 좋은 것)을 연하게 표시
  const best = (f: (c: Col) => number | null | undefined): string | null => {
    const v = cols.map((c) => [c.id, f(c)] as const).filter(([, x]) => x != null) as [string, number][];
    if (v.length < 2 || v.every(([, x]) => x === v[0][1])) return null;
    return v.reduce((a, b) => (b[1] < a[1] ? b : a))[0];
  };
  const rows: {
    label: string;
    cell: (c: Col) => React.ReactNode;
    best?: string | null;
    pcOnly?: boolean;
  }[] = [
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
    {
      label: t.rows.market,
      cell: (c) => (marketRatio(c) != null ? `${marketRatio(c)}%` : t.unknown),
      best: best(marketRatio),
      pcOnly: true,
    },
    {
      label: t.rows.unknown,
      cell: (c) => (c.d ? `${c.d.unknown_count}개` : "-"),
      best: best((c) => c.d?.unknown_count),
      pcOnly: true,
    },
    {
      label: t.rows.fail,
      cell: (c) => (failHit(c) != null ? `${failHit(c)}개` : "-"),
      best: best(failHit),
      pcOnly: true,
    },
    {
      label: t.rows.field,
      cell: (c) => (c.w ? t.checked(Object.keys(c.w.checks).length) : "-"),
      pcOnly: true,
    },
    {
      label: t.rows.mine,
      cell: (c) =>
        c.w && c.w.calcs.length ? c.w.calcs.map((x) => won(x.bid_krw)).join(" · ") : t.none,
      pcOnly: true,
    },
    { label: t.rows.step, cell: (c) => (c.w ? copy.watch.steps[c.w.step] : "-"), pcOnly: true },
  ];
  const shownRows = rows.filter((r) => pc || more || !r.pcOnly);
  const blank = pc && data ? Math.max(0, data.max - cols.length) : 0;

  return (
    <main className="page compare-page">
      <PageHeader
        title={t.title}
        back="/watch"
        right={data ? <span className="sub">{cols.length}/{data.max}</span> : undefined}
      />
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
                {Array.from({ length: blank }, (_, i) => (
                  <th key={`b${i}`} className="sub" style={{ fontWeight: 400 }}>
                    <Link href="/watch">{t.addMore} ›</Link>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shownRows.map((r) => (
                <tr key={r.label}>
                  <td className="sub">{r.label}</td>
                  {cols.map((c) => (
                    <td key={c.id} className={r.best === c.id ? "best" : ""}>
                      {r.cell(c)}
                    </td>
                  ))}
                  {Array.from({ length: blank }, (_, i) => (
                    <td key={`b${i}`} />
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
      {cols.length > 0 && !pc && (
        <button className="cond-row" onClick={() => setMore(!more)}>
          <span>{more ? t.less : t.more}</span>
          <span className="sub">{more ? "▴" : "›"}</span>
        </button>
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
