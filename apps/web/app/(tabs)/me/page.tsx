"use client";

import { useFresh } from "@/lib/api/fresh";
import { Delayed, SkListPage, SkSection } from "@/components/skeleton";
import { LoadError } from "@/components/load-error";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { NeedLogin } from "@/components/need-login";
import {
  meApi,
  type Bid,
  type BidIn,
  type BidTodo,
  type Bids,
  type Mock,
  type WatchCard,
} from "@/lib/api/me";
import { PageHeader } from "@/components/layout/page-header";
import { useIsPc } from "@/lib/use-pc";
import { DDay } from "@/components/dday";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { fetchCourtBidders, type CourtBidders } from "@/lib/api/items";
import { won } from "@/lib/format";

const t = copy.me;
const num = (s: string) => (s ? Number(s.replace(/[^0-9]/g, "")) || null : null);
// 금액 칸은 만 원 단위(11/1 — 예전엔 원 단위라 「38000」이 3만 8천 원으로 저장됐음)
const man = (s: string) => {
  const n = num(s);
  return n ? n * 10_000 : null;
};
const md = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;

// 결과 기록(RESULT-01): 결과 하나 고르고, 숫자는 아는 것만.
function RecordForm({ x, onSaved, token }: { x: BidTodo; onSaved: () => void; token: string }) {
  const [outcome, setOutcome] = useState<string | null>(null);
  const [f, setF] = useState({ my: "", win: "", second: "", n: "", pay: "" });
  const [done, setDone] = useState<CourtBidders | null>(null);
  const bid = outcome === "won" || outcome === "lost";
  const save = () => {
    const b: BidIn = {
      item_id: x.item_id,
      sale_date: x.sale_date,
      outcome: outcome!,
      my_bid_krw: man(f.my),
      winning_bid_krw: outcome === "won" ? man(f.my) : man(f.win),
      second_bid_krw: man(f.second),
      bidder_count: num(f.n),
      pay_date: f.pay || null,
    };
    // 남기면 바로 이 법원 응찰자 수부터 보여 줌(기록이 쌓이는 보람)
    meApi
      .saveBid(token, b)
      .then(() => fetchCourtBidders(x.item_id))
      .then(setDone)
      .catch(onSaved);
  };
  if (done)
    return (
      <div className="py-12 px-0">
        <div className="fw-6">{t.thanks}</div>
        <div className="bg-panel r-14 p-12 mt-8 fs-md">
          {done.avg != null ? t.thanksBidders(done.avg, done.n) : t.thanksWait(done.n, done.min_n)}
        </div>
        <div className="d-flex jc-between ai-center mt-10">
          <Link href="/pro/market" className="link">
            {t.toScore}
          </Link>
          <button className="btn secondary sm" onClick={onSaved}>
            {t.ok}
          </button>
        </div>
      </div>
    );
  const input = (k: keyof typeof f, label: string, type = "text", money = false) => (
    <label className="d-block fs-sm mt-8">
      <span className="sub m-0">
        {label}
        {money ? ` (${t.manUnit})` : ""}
        {money && man(f[k]) ? ` = ${won(man(f[k]))}` : ""}
      </span>
      <input
        type={type}
        inputMode={type === "text" ? "numeric" : undefined}
        value={f[k]}
        onChange={(e) => setF({ ...f, [k]: e.target.value })}
        className="f-input"
      />
    </label>
  );
  return (
    <div className="py-12 px-0">
      <div className="fw-6">
        {x.place} <span className="sub">· {md(x.sale_date)}</span>
      </div>
      <div className="d-flex gap-6 f-wrap mt-8">
        {Object.entries(t.outcome).map(([k, v]) => (
          <button
            key={k}
            className={`pill${outcome === k ? " on" : ""}`}
            onClick={() => setOutcome(k)}
          >
            {v}
          </button>
        ))}
      </div>
      {bid && (
        <>
          {input("my", t.myBid, "text", true)}
          {outcome === "lost" && input("win", t.winning, "text", true)}
          {input("second", t.second, "text", true)}
          {input("n", t.bidders)}
          {outcome === "won" && input("pay", t.payDate, "date")}
        </>
      )}
      {outcome && (
        <button className="btn primary mt-10 w-full" onClick={save}>
          {t.save}
        </button>
      )}
    </div>
  );
}

// 낙찰 받은 물건: 세 날짜 요약 + 마감만.
function WonCard({ b }: { b: Bid }) {
  const s = b.schedule!;
  const rng = (a: [string, string]) => `${md(a[0])} ~ ${md(a[1])}`;
  return (
    <div className="py-12 px-0">
      <Link href={`/item/${b.item_id}`} className="link in fw-6">
        {b.place}
      </Link>
      <div className="sub m-0">
        {b.case_no} · {won(b.my_bid_krw)}
      </div>
      {[md(s.summary.pay), rng(s.summary.move_out), rng(s.summary.forced)].map((v, i) => (
        <div key={i} className="d-flex jc-between fs-md py-4 px-0">
          <span>{t.summary[i]}</span>
          <b>{v}</b>
        </div>
      ))}
      {s.pay_estimated && <div className="sub">{t.payGuess}</div>}
      <div className="mt-6">
        {s.rows
          .filter((r) => r.deadline && r.key !== "pay")
          .map((r) => (
            <div key={r.key} className="fs-sm c-amber">
              ◆ {r.label} {r.short}
            </div>
          ))}
      </div>
    </div>
  );
}

export default function Me() {
  const { session, ready } = useSession();
  const [d, setD] = useState<Bids | null>(null);
  const [mocks, setMocks] = useState<Mock[]>([]);
  const [watch, setWatch] = useState<WatchCard[]>([]);
  const pc = useIsPc();
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    if (!session) return;
    setFailed(false);
    // 관심·입찰 기록·모의입찰을 한 번에(11/3 — 예전 3번)
    meApi
      .auction(session.access_token)
      .then((a) => {
        setWatch(a.watch);
        setD(a.bids);
        setMocks(a.mocks);
      })
      .catch(() => setFailed(true));
  }, [session]);
  const fresh = useFresh();
  useEffect(load, [load, fresh]);

  if (!ready)
    return (
      <main className="page">
        <SkListPage cards={false} />
      </main>
    );
  if (!session) return <NeedLogin title={copy.tabs.me} />;
  if (failed && !d)
    return (
      <main className="page">
        <PageHeader title={copy.tabs.me} />
        <LoadError onRetry={load} />
      </main>
    );
  if (!d)
    return (
      <main className="page">
        <PageHeader title={copy.tabs.me} />
        <Delayed>
          <SkSection rows={2} />
          <SkSection rows={3} />
        </Delayed>
      </main>
    );
  const empty = d && !d.won.length && !d.history.length && !d.todo.length && !mocks.length;
  const dropMock = (id: number) => {
    setMocks((l) => l.filter((x) => x.mock_id !== id));
    meApi.removeMock(session.access_token, id).catch(() => {});
  };
  const upcoming = watch
    .filter((w) => w.d_day != null && w.d_day >= 0 && w.step !== "result" && w.step !== "after")
    .sort((x, y) => (x.d_day ?? 99) - (y.d_day ?? 99));
  const box = (title: string, hint: string | null, children: React.ReactNode, show: boolean) =>
    show || pc ? (
      <section className="section">
        <h2 className="fs-base m-0">{title}</h2>
        {hint && <p className="sub mt-4 mb-0 mx-0">{hint}</p>}
        {children}
      </section>
    ) : null;

  const upcomingBox = box(
    t.upcoming,
    null,
    upcoming.length === 0 ? (
      <p className="sub">{t.upcomingEmpty}</p>
    ) : (
      upcoming.map((w) => (
        <Link
          key={w.item_id}
          href={
            w.d_day != null && w.d_day <= 1
              ? `/item/${encodeURIComponent(w.item_id)}/bid-day`
              : `/watch/${encodeURIComponent(w.item_id)}`
          }
          className="menu-row"
        >
          <span className="minw-0">
            <DDay d={w.d_day} /> {w.sale_date?.slice(5).replace("-", "/")} · {w.place}{" "}
            {w.building ?? w.usage}
            <span className="sub d-block">
              {copy.watch.steps[w.step]} · {w.court} {w.case_no}
            </span>
          </span>
          <span className="sub">›</span>
        </Link>
      ))
    ),
    upcoming.length > 0,
  );

  const recordBox = box(
    t.recordTitle,
    d && d.todo.length > 0 ? t.todoHint : null,
    <>
      {d?.todo.map((x) => (
        <div key={x.item_id} id={`rec-${x.item_id}`}>
          <RecordForm x={x} token={session.access_token} onSaved={load} />
        </div>
      ))}
      {d && d.todo.length === 0 && d.history.length === 0 && <p className="sub">{t.recordEmpty}</p>}
      {d && d.history.length > 0 && (
        <div className="m-block mt-8">
          {d.history.map((b) => (
            <div key={b.bid_id} className="py-10 px-0">
              <div className="d-flex jc-between gap-8 fs-md">
                <span className="fw-6">{b.place}</span>
                <span className="sub nowrap">{t.outcome[b.outcome]}</span>
              </div>
              <div className="sub fs-xs">
                {[
                  b.my_bid_krw ? `${t.cols.my} ${won(b.my_bid_krw)}` : "",
                  b.winning_bid_krw ? `${t.cols.win} ${won(b.winning_bid_krw)}` : "",
                  b.second_bid_krw ? `${t.cols.second} ${won(b.second_bid_krw)}` : "",
                  b.bidder_count != null ? `${t.cols.n} ${b.bidder_count}명` : "",
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            </div>
          ))}
        </div>
      )}
      {d && d.history.length > 0 && (
        <div className="pc-only ox-auto mt-8">
          <table className="pro-table wrap-first">
            <thead>
              <tr>
                <th>{t.cols.place}</th>
                <th>{t.cols.outcome}</th>
                <th>{t.cols.my}</th>
                <th>{t.cols.win}</th>
                <th>{t.cols.second}</th>
                <th>{t.cols.n}</th>
              </tr>
            </thead>
            <tbody>
              {d.history.map((b) => (
                <tr key={b.bid_id}>
                  <td>{b.place}</td>
                  <td>{t.outcome[b.outcome]}</td>
                  <td>{won(b.my_bid_krw)}</td>
                  <td>{won(b.winning_bid_krw)}</td>
                  <td>{won(b.second_bid_krw)}</td>
                  <td>{b.bidder_count != null ? `${b.bidder_count}명` : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>,
    Boolean(d && (d.todo.length > 0 || d.history.length > 0)),
  );

  const mockBox = box(
    copy.mock.notes,
    copy.mock.notesHint,
    <>
      {mocks.length === 0 && <p className="sub">{t.mockEmpty}</p>}
      {mocks.map((x) => (
        <div key={x.mock_id} className="py-10 px-0">
          <div className="d-flex jc-between gap-8">
            <Link href={`/item/${encodeURIComponent(x.item_id)}`} className="link in fw-6 fs-md">
              {x.place} <span className="sub">{md(x.sale_date)}</span>
            </Link>
            <button className="btn secondary sm" onClick={() => dropMock(x.mock_id)}>
              {copy.mock.remove}
            </button>
          </div>
          <div className="sub">
            {x.decision === "skip" ? copy.mock.skip : `${copy.mock.amount} ${won(x.bid_krw ?? 0)}`}
            {x.max_krw ? ` · 상한 ${won(x.max_krw)}` : ""}
            {x.reason ? ` · ${x.reason}` : ""}
          </div>
          {x.review.map((line) => (
            <div key={line} className="fs-md mt-2">
              {line}
            </div>
          ))}
          {(x.similar?.length ?? 0) > 0 && (
            <div className="bg-panel r-14 p-12 mt-8">
              <div className="fs-sm fw-7 mb-4">{copy.mock.similar}</div>
              {x.similar?.map((s) => (
                <Link
                  key={s.item_id}
                  href={`/item/${encodeURIComponent(s.item_id)}`}
                  className="line-row go c-inherit fs-md"
                >
                  <span className="ellipsis minw-0">
                    {s.place} <span className="sub">{md(s.sale_date)}</span>
                  </span>
                  <b className="nowrap">{won(s.min_price_krw)}</b>
                </Link>
              ))}
            </div>
          )}
        </div>
      ))}
    </>,
    mocks.length > 0,
  );

  const wonBox = box(
    t.won,
    null,
    <>
      {d && d.won.length === 0 && <p className="sub">{t.wonEmpty}</p>}
      {d?.won.map((b) => (
        <WonCard key={b.bid_id} b={b} />
      ))}
    </>,
    Boolean(d && d.won.length > 0),
  );

  return (
    <main className="page">
      <PageHeader title={t.title} />
      {empty && !pc && (
        <section className="section">
          <p className="sub">{t.empty}</p>
        </section>
      )}
      {pc ? (
        <div className="pc-grid g-2x2">
          {upcomingBox}
          {recordBox}
          {mockBox}
          {wonBox}
        </div>
      ) : (
        <>
          {upcomingBox}
          {recordBox}
          {wonBox}
          {mockBox}
        </>
      )}
    </main>
  );
}
