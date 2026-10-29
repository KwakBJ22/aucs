"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CalcBox, Row } from "@/components/calc-box";
import { PageHeader } from "@/components/layout/page-header";
import { fetchItem, type ItemDetail } from "@/lib/api/items";
import { meApi, type Workspace } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";

const t = copy.calcPage;

// 입찰가 계산(PC-CALC): 왼쪽 계산 전부 60 · 오른쪽 이 물건 숫자·예상 낙찰 범위·저장한 계산 40
export default function CalcPage() {
  const id = decodeURIComponent(String(useParams().id));
  const eid = encodeURIComponent(id);
  const { session } = useSession();
  const [d, setD] = useState<ItemDetail | null>(null);
  const [w, setW] = useState<Workspace | null>(null);
  useEffect(() => {
    fetchItem(id)
      .then(setD)
      .catch(() => setD(null));
  }, [id]);
  useEffect(() => {
    if (session)
      meApi
        .workspace(session.access_token, id)
        .then(setW)
        .catch(() => setW(null));
  }, [session, id]);
  const worth = d?.questions.find((q) => q.key === "worth");
  const range = worth?.body?.range_krw as [number, number] | undefined;
  const market = worth?.body?.market as { price_krw: number; n: number } | undefined;
  return (
    <main className="page">
      <PageHeader
        title={t.title}
        back={`/item/${eid}`}
        sub={d ? `${d.court} ${d.case_no} · ${d.place} ${d.building ?? d.usage ?? ""}` : undefined}
      />
      <div className="pc-grid g-60-40">
        <section className="section mt-0">
          <CalcBox id={id} />
        </section>
        <div className="pc-sticky">
          {d && (
            <section className="section mt-0">
              <h2>{t.numbers}</h2>
              <Row label={copy.item.pc.sale} value={`${dday(d.d_day)} ${d.sale_date ?? ""}`} />
              <Row label={copy.item.pc.appraisal} value={won(d.appraisal_krw)} />
              <Row label={copy.item.pc.min} value={`${won(d.min_price_krw)} (${d.min_rate}%)`} />
              {d.next_round.min_price_krw && (
                <Row label={copy.item.nextRound} value={won(d.next_round.min_price_krw)} />
              )}
              {market && <Row label={copy.item.market(market.n)} value={won(market.price_krw)} />}
              {range && (
                <Row label={copy.item.rangeLabel} value={`${won(range[0])} ~ ${won(range[1])}`} />
              )}
              <div className="sub mt-6">{worth?.answer}</div>
            </section>
          )}
          <section className="section">
            <h2>{copy.ws.bids}</h2>
            {!session && <p className="sub">{t.loginForSaved}</p>}
            {session && (!w || w.calcs.length === 0) && <p className="sub">{t.savedNone}</p>}
            {w?.calcs.map((x) => (
              <div key={x.bid_krw} className="line-row fs-md">
                <b>{won(x.bid_krw)}</b>
                <span className="sub">
                  {x.cash_krw ? copy.ws.cashNeed(won(x.cash_krw)) : ""} · {x.saved_at}
                </span>
              </div>
            ))}
          </section>
          <section className="section">
            <Link href={`/item/${eid}/bid-sheet`} className="menu-row">
              <span>{copy.bidSheet.title}</span>
              <span className="sub">›</span>
            </Link>
            <Link href="/pro/market" className="menu-row">
              <span>{copy.item.pc.market}</span>
              <span className="sub">›</span>
            </Link>
          </section>
        </div>
      </div>
    </main>
  );
}
