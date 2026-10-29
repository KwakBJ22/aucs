"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { HeartButton } from "@/components/heart-button";
import { fetchItem, isOnbid, type ItemDetail, type OnbidDetail } from "@/lib/api/items";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";

const t = copy.find;
const TONE: Record<string, string> = {
  green: "var(--green)",
  gray: "var(--faint)",
  orange: "var(--amber)",
  red: "var(--red)",
  blue: "var(--blue)",
};

// PC 오른쪽(찾기·전체 물건): 고른 물건의 다섯 질문 한 줄씩 + 담기·비교·상세
export function PickPanel({ id }: { id: string | null }) {
  const [d, setD] = useState<ItemDetail | OnbidDetail | null>(null);
  const { session } = useSession();
  const [msg, setMsg] = useState("");
  useEffect(() => {
    setD(null);
    setMsg("");
    if (id)
      fetchItem(id)
        .then((x) => setD(x as ItemDetail | OnbidDetail))
        .catch(() => setD(null));
  }, [id]);
  if (!id)
    return (
      <section className="section">
        <p className="sub">{t.pickEmpty}</p>
      </section>
    );
  if (!d) return <section className="section" style={{ height: 260, opacity: 0.5 }} />;
  const eid = encodeURIComponent(d.item_id);
  // 공매는 다섯 질문 대신 공매 상세의 줄(10/29 — 공매를 고르면 화면이 멈추던 것)
  const qs = isOnbid(d)
    ? [
        {
          key: "buy",
          title: copy.onbid.q.buy,
          answer: [d.kind_name, d.usage].filter(Boolean).join(" · "),
          tone: "gray",
        },
        {
          key: "hold",
          title: copy.onbid.q.hold,
          answer: copy.onbid.holdAnswer,
          tone: d.kind === "trust" ? "orange" : "red",
        },
        {
          key: "check",
          title: copy.onbid.q.check,
          answer: copy.onbid.checkAnswer(d.check_left),
          tone: "orange",
        },
      ]
    : d.questions;
  return (
    <section className="section">
      <div className="sub" style={{ margin: 0 }}>
        <b style={{ color: "var(--amber)" }}>{dday(d.d_day)}</b> · {d.sale_date} ·{" "}
        {isOnbid(d) ? copy.onbid.badge(d.kind_name ?? "") : d.court} {d.case_no}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <h2 style={{ marginTop: 4 }}>
          {d.place} {(isOnbid(d) ? null : d.building) ?? d.usage}
        </h2>
        <HeartButton id={d.item_id} />
      </div>
      <div style={{ fontSize: 24, fontWeight: 700 }}>
        {won(d.min_price_krw)}{" "}
        <span className="sub">
          {d.min_rate}% · 감정가 {won(d.appraisal_krw)}
        </span>
      </div>
      {d.fatal && <div className="fatal">{d.fatal}</div>}
      <p style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.5 }}>{d.verdict}</p>
      {qs.map((q) => (
        <Link key={q.key} href={`/item/${eid}#q-${q.key}`} className="menu-row">
          <span style={{ display: "flex", gap: 8, alignItems: "baseline", minWidth: 0 }}>
            <span className="toc-dot" style={{ background: TONE[q.tone] ?? "var(--faint)" }} />
            <span>
              <span className="sub" style={{ display: "block", margin: 0, fontSize: 12 }}>
                {q.title}
              </span>
              {q.answer}
            </span>
          </span>
          <span className="sub">›</span>
        </Link>
      ))}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <Link
          href={`/item/${eid}`}
          className="btn primary"
          style={{ height: 44, fontSize: 15, flex: 2 }}
        >
          {t.toDetail}
        </Link>
        {session && (
          <button
            className="pc-act"
            style={{ flex: 1 }}
            onClick={() =>
              meApi
                .addCompare(session.access_token, d.item_id)
                .then(() => setMsg(copy.compare.added))
                .catch(() => setMsg(copy.compare.full(5)))
            }
          >
            {msg || copy.compare.add}
          </button>
        )}
      </div>
    </section>
  );
}
