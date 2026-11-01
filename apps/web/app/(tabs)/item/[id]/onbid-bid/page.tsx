"use client";

import { copyText } from "@/lib/copy-text";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import { fetchBidCheck, fetchItem, type BidCheck, type OnbidDetail } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";

// 온비드 입찰 준비(GM-02, 설계서 3절). 경매 입찰표·입찰일 아침 대신. 입찰 자체는 온비드에서 손님이 함.
const t = copy.onbidBid;
const KEY = (id: string) => `aucs_onbid_ready_${id}`; // 준비물 체크는 이 기기에만
const WD = ["일", "월", "화", "수", "목", "금", "토"];

function when(iso: string | null): string {
  if (!iso) return "";
  const k = new Date(new Date(iso).getTime() + 9 * 3600_000);
  return `${k.getUTCMonth() + 1}월 ${k.getUTCDate()}일(${WD[k.getUTCDay()]}) ${k.getUTCHours()}시`;
}

export default function OnbidBid() {
  const id = decodeURIComponent(String(useParams().id));
  const [d, setD] = useState<OnbidDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [bidMan, setBidMan] = useState("");
  const [chk, setChk] = useState<BidCheck | null>(null);
  const [ready, setReady] = useState<boolean[]>([false, false, false]);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchItem(id)
      .then((x) => {
        const o = x as unknown as OnbidDetail;
        setD(o);
        // 처음엔 「혼자 들어갈 때 가운데값」으로 넣어 둠 — 손님이 바꿈
        const solo = o.expected.find((e) => e.bucket === "혼자")?.price_krw ?? o.min_price_krw;
        if (solo) setBidMan(String(Math.ceil(solo / 10_000)));
      })
      .catch(() => setFailed(true));
    try {
      const v = JSON.parse(localStorage.getItem(KEY(id)) ?? "null") as boolean[] | null;
      if (Array.isArray(v) && v.length === 3) setReady(v);
    } catch {
      /* 저장 못 해도 계속 */
    }
  }, [id]);

  const bid = Number(bidMan.replace(/[^0-9]/g, "")) * 10_000;
  useEffect(() => {
    if (!bid) return setChk(null);
    const h = setTimeout(() => {
      fetchBidCheck(id, bid)
        .then(setChk)
        .catch(() => setChk(null));
    }, 300);
    return () => clearTimeout(h);
  }, [id, bid]);

  const tick = (i: number) => {
    const next = ready.map((v, j) => (j === i ? !v : v));
    setReady(next);
    try {
      localStorage.setItem(KEY(id), JSON.stringify(next));
    } catch {
      /* 저장 못 해도 계속 */
    }
  };

  if (failed)
    return (
      <main className="page narrow">
        <PageHeader title={t.title} back={`/item/${encodeURIComponent(id)}`} />
        <LoadError onRetry={() => location.reload()} />
      </main>
    );
  if (!d) return <main className="page narrow" aria-busy="true" />;
  const items = [t.ready[0], t.ready[1](won(d.deposit_krw)), t.ready[2]];
  const levelColor =
    chk?.level === "block"
      ? "var(--red)"
      : chk?.level === "stop"
        ? "var(--orange)"
        : "var(--green)";

  return (
    <main className="page narrow">
      <PageHeader title={t.title} back={`/item/${encodeURIComponent(id)}`} />
      <section className="section">
        <div className="sub m-0">
          {d.bid_end ? t.closesAt(when(d.bid_end)) : copy.onbid.undecided}
        </div>
        <div className="fs-3xl fw-7 mt-4">
          {d.d_day != null ? t.left(dday(d.d_day), d.d_day) : ""}
        </div>
        <div className="fs-base mt-4">
          {d.place} {d.usage ?? ""} · {d.case_no}
        </div>
      </section>

      <section className="section">
        <h2>{t.readyTitle}</h2>
        {items.map((label, i) => (
          <label key={i} className="d-flex gap-10 ai-center py-10 px-0 fs-base mh-44">
            <input
              type="checkbox"
              checked={ready[i]}
              onChange={() => tick(i)}
              style={{ width: 20, height: 20 }}
            />
            {label}
          </label>
        ))}
      </section>

      <section className="section">
        <h2>{t.bidTitle}</h2>
        <label className="d-flex ai-baseline gap-6 mt-8">
          <input
            inputMode="numeric"
            value={bidMan}
            onChange={(e) => setBidMan(e.target.value.replace(/[^0-9]/g, ""))}
            aria-label={t.bidLabel}
            className="f-1 minw-0 fs-2xl fw-7 py-10 px-12 b-0 r-14 bg-panel c-inherit"
          />
          <span className="sub">{t.man}</span>
        </label>
        {chk && (
          <>
            <div className="fs-sm mt-6">{chk.korean}</div>
            <div className="fs-md mt-6 fw-6" style={{ color: levelColor }}>
              {chk.message}
            </div>
          </>
        )}
        <p className="sub fs-xs mt-8">{t.bidNote}</p>
      </section>

      <section className="section">
        <h2>{t.stepsTitle}</h2>
        <ol className="m-0 pl-20 lh-16 fs-md">
          <li>{t.steps[0]}</li>
          <li>
            {t.steps[1]}{" "}
            <button
              className="chip gray b-0 mh-28"
              onClick={() =>
                void copyText(d.case_no).then(
                  () => setCopied(true),
                  () => setCopied(false),
                )
              }
            >
              {copied ? copy.onbid.copied : d.case_no}
            </button>
          </li>
          <li>{t.steps[2]}</li>
          <li>{t.steps[3]}</li>
          <li>{t.steps[4]}</li>
        </ol>
      </section>

      <a className="btn primary" href={copy.onbid.onbidUrl} target="_blank" rel="noreferrer">
        {t.go}
      </a>
      <p className="sub ta-center fs-xs mt-10 mb-24 mx-0">{t.foot}</p>
    </main>
  );
}
