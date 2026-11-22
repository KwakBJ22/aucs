"use client";

import { Delayed, SkLines } from "@/components/skeleton";
import Link from "next/link";
import { useEffect, useState } from "react";
import { HeartButton } from "@/components/heart-button";
import { fetchItem, isOnbid, type ItemDetail, type OnbidDetail } from "@/lib/api/items";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";
import { DDay } from "@/components/dday";

const t = copy.find;
// PC 오른쪽(찾기·전체 물건): 고른 물건의 다섯 질문 한 줄씩 + 담기·비교·상세
export function PickPanel({ id }: { id: string | null }) {
  const [d, setD] = useState<ItemDetail | OnbidDetail | null>(null);
  const { session } = useSession();
  const [msg, setMsg] = useState("");
  useEffect(() => {
    setD(null);
    setMsg("");
    if (id && session)
      fetchItem(id)
        .then((x) => setD(x as ItemDetail | OnbidDetail))
        .catch(() => setD(null));
  }, [id, session]);
  if (!id || !session)
    return (
      <section className="section">
        <p className="sub">{id ? t.pickLogin : t.pickEmpty}</p>
      </section>
    );
  if (!d)
    return (
      <section className="section">
        <Delayed>
          <SkLines n={2} />
          <div className="mt-16">
            <SkLines n={5} />
          </div>
        </Delayed>
      </section>
    );
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
  // 판정 한 줄 색(11/22 디자인): 빨간 신호가 있으면 빨강, 없으면 초록
  const red = Boolean(d.fatal) || qs.some((q) => q.tone === "red");
  return (
    <section className="section pick-panel">
      <div className="sub m-0">
        <DDay d={d.d_day} /> · {d.sale_date} ·{" "}
        {isOnbid(d) ? copy.onbid.badge(d.kind_name ?? "") : d.court} {d.case_no}
      </div>
      <div className="d-flex jc-between gap-8">
        <h2 className="mt-4 pp-title">
          {d.place} {(isOnbid(d) ? null : d.building) ?? d.usage}
        </h2>
        <HeartButton id={d.item_id} />
      </div>
      <div className="pp-price">
        {won(d.min_price_krw)}{" "}
        <span className="sub">
          {d.appraisal_krw ? `${d.min_rate}% · 감정가 ${won(d.appraisal_krw)}` : ""}
        </span>
      </div>
      {d.fatal && <div className="fatal">{d.fatal}</div>}
      <p className={`pp-verdict${red ? " red" : " ok"}`}>{d.verdict}</p>
      {/* 다섯 질문: 작은 질문 + 굵은 답 한 줄(11/22 디자인 — 색 점은 뺌) */}
      {qs.map((q) => (
        <Link key={q.key} href={`/item/${eid}#q-${q.key}`} className="menu-row go pp-q">
          <span className="minw-0">
            <span className="sub d-block m-0">{q.title}</span>
            <b>{q.answer}</b>
          </span>
        </Link>
      ))}
      <div className="pp-btns">
        <Link prefetch={false} href={`/item/${eid}`} className="btn primary md">
          {t.toDetail}
        </Link>
        {session && (
          <button
            className="pc-act f-1"
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
