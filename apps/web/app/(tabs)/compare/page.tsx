"use client";

import { Delayed, SkListPage, SkTable } from "@/components/skeleton";
import { LoadError } from "@/components/load-error";
import Link from "next/link";
import { useEffect, useState } from "react";
import { NeedLogin } from "@/components/need-login";
import { isOnbid, type Calc, type ItemDetail, type OnbidDetail } from "@/lib/api/items";
import { meApi, type Compare, type Workspace } from "@/lib/api/me";
import { PageHeader } from "@/components/layout/page-header";
import { useIsPc } from "@/lib/use-pc";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { loadProfile } from "@/lib/profile";

const t = copy.compare;
type Col = {
  id: string;
  d: ItemDetail | OnbidDetail | null;
  calc: Calc | null;
  w: Workspace | null;
};
const ob = copy.onbid;
const REASONS = ["budget", "assumed_unclear", "field_bad", "other"] as const;

// 공매는 다섯 질문 대신 공매 상세 값으로 같은 줄을 채움
const answer = (d: ItemDetail | OnbidDetail | null, key: string): string => {
  if (!d) return "-";
  if (isOnbid(d)) {
    const solo = d.expected.find((e) => e.bucket === "혼자");
    if (key === "hold") return ob.holdAnswer;
    if (key === "worth")
      return ob.worthAnswer(
        d.market ? won(d.market.price_krw) : null,
        solo?.price_krw ? won(solo.price_krw) : null,
      );
    if (key === "check") return ob.checkAnswer(d.check_left);
    return "-";
  }
  return d.questions.find((q) => q.key === key)?.answer ?? "-";
};

// 비교함: 같은 기준으로 3~5개 나란히. 뺄 때 이유를 남김(다음 추천에서 덜 보여 줌)
export default function ComparePage() {
  const { session, ready } = useSession();
  const token = session?.access_token ?? null;
  const [data, setData] = useState<Compare | null>(null);
  const [cols, setCols] = useState<Col[]>([]);
  const [asking, setAsking] = useState<string | null>(null);
  const [more, setMore] = useState(false);
  const [failed, setFailed] = useState(false);
  const pc = useIsPc();

  // 담은 물건마다 상세·계산·작업 공간을 한 번에(10/27 — 예전엔 1 + 물건 수 × 3번)
  const load = (tok: string) => {
    const p = loadProfile();
    return meApi
      .compareFull(tok, p?.homes ?? 0, Boolean(p?.firstTime))
      .then(({ cols: c, ...rest }) => {
        setFailed(false);
        setData(rest);
        setCols(c);
      })
      .catch(() => setFailed(true));
  };

  useEffect(() => {
    if (token) void load(token);
  }, [token]);

  if (!ready)
    return (
      <main className="page">
        <SkListPage />
      </main>
    );
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
    if (c.d && isOnbid(c.d)) return c.d.market_rate ?? null;
    const m = (c.d as ItemDetail | null)?.questions.find((q) => q.key === "worth")?.body?.market
      ?.price_krw as number | undefined;
    return m && c.d?.min_price_krw ? Math.round((c.d.min_price_krw * 100) / m) : null;
  };
  const failHit = (c: Col): number | null =>
    c.d && !isOnbid(c.d) && c.d.failure_table
      ? c.d.failure_table.filter((r) => r.state === "걸림" || r.state === "확인 필요").length
      : null;
  // 줄마다 가장 나은 값(작을수록 좋은 것)을 연하게 표시
  const best = (f: (c: Col) => number | null | undefined): string | null => {
    const v = cols.map((c) => [c.id, f(c)] as const).filter(([, x]) => x != null) as [
      string,
      number,
    ][];
    if (v.length < 2 || v.every(([, x]) => x === v[0]![1])) return null;
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
      cell: (c) =>
        c.d
          ? isOnbid(c.d)
            ? `${dday(c.d.d_day)} · ${ob.closeShort(c.d.bid_end ?? null)}`
            : `${dday(c.d.d_day)} · ${c.d.sale_date?.slice(5) ?? ""}`
          : "-",
    },
    {
      label: t.rows.min,
      cell: (c) =>
        c.d ? (
          <>
            <b>{won(c.d.min_price_krw)}</b>
            {c.d.min_rate != null && (
              <div className="sub">
                {copy.card.ofAppraisal} {c.d.min_rate}%
              </div>
            )}
          </>
        ) : (
          "-"
        ),
    },
    {
      label: t.rows.cash,
      cell: (c) => {
        const o = c.d && !isOnbid(c.d) ? (c.d as ItemDetail).outcome : null;
        if (o?.closed)
          // 끝난 물건은 계산 대신 결과(11/1)
          return o.code === "sold" && o.winning_bid_krw
            ? copy.outcome.sold(o.date.slice(5).replace("-", "/"), won(o.winning_bid_krw), o.rate)
            : copy.outcome.other(o.date.slice(5).replace("-", "/"), o.text);
        return c.calc ? (
          <>
            <b>{won(c.calc.selected.cash_krw)}</b>
            <div className="sub">{t.atBid(won(c.calc.selected.bid_krw))}</div>
          </>
        ) : (
          "-"
        );
      },
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
      cell: (c) => (c.d && !isOnbid(c.d) ? `${c.d.unknown_count}개` : "-"),
      best: best((c) => (c.d && !isOnbid(c.d) ? c.d.unknown_count : null)),
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
        right={
          data ? (
            <span className="sub">
              {cols.length}/{data.max}
            </span>
          ) : undefined
        }
      />
      {failed && !data && <LoadError onRetry={() => token && void load(token)} />}
      {!failed && !data && token && (
        <Delayed>
          <section className="section">
            <SkTable rows={8} cols={3} />
          </section>
        </Delayed>
      )}
      {data && data.items.length === 0 && (
        <section className="section">
          <p className="sub">{t.empty}</p>
          <Link href="/watch" className="link">
            {copy.watch.title}
          </Link>
        </section>
      )}
      {cols.length > 0 && (
        <section className="section p-0 ox-auto">
          <table className="compare-table">
            <thead>
              <tr>
                <th />
                {cols.map((c) => (
                  <th key={c.id}>
                    <Link
                      prefetch={false}
                      href={`/item/${encodeURIComponent(c.id)}`}
                      className="d-flex ai-center go c-inherit"
                    >
                      <span className="minw-0">
                        <div className="sub">
                          {c.d && isOnbid(c.d) ? ob.badge(c.d.kind_name ?? "") : c.d?.court}{" "}
                          {c.d?.case_no}
                        </div>
                        <div className="fw-6">
                          {c.d?.place} {(c.d && !isOnbid(c.d) ? c.d.building : null) ?? c.d?.usage}
                        </div>
                      </span>
                    </Link>
                    {c.d?.fatal && <div className="fatal">{c.d.fatal}</div>}
                  </th>
                ))}
                {Array.from({ length: blank }, (_, i) => (
                  <th key={`b${i}`} className="sub fw-4">
                    <Link href="/watch" className="link">
                      {t.addMore}
                    </Link>
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
                      <div className="d-flex f-col gap-6">
                        <span className="sub">{t.why}</span>
                        {REASONS.map((r) => (
                          <button
                            key={r}
                            className="btn secondary sm"
                            onClick={() => exclude(c.id, r)}
                          >
                            {t.reasons[r]}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <button className="btn secondary sm" onClick={() => setAsking(c.id)}>
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
        <button className="cond-row fold" aria-expanded={more} onClick={() => setMore(!more)}>
          <span>{more ? t.less : t.more}</span>
        </button>
      )}
      {cols.length > 0 && <div className="sub">{t.note}</div>}
      {data && data.excluded.length > 0 && (
        <section className="section">
          <h2>{t.excluded}</h2>
          {data.excluded.map((e) => (
            <div key={e.item_id} className="d-flex jc-between ai-center py-8 px-0 fs-md">
              <span>
                {e.place}
                <span className="sub d-block">
                  {e.case_no} · {t.reasons[e.reason as (typeof REASONS)[number]] ?? e.reason} ·{" "}
                  {e.at}
                </span>
              </span>
              <button className="btn secondary sm" onClick={() => undo(e.item_id)}>
                {t.undo}
              </button>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
