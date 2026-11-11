"use client";

import Link from "next/link";
import { useState } from "react";
import { HeartButton } from "./heart-button";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { DDay } from "@/components/dday";
import type { ItemCard as Card } from "@/lib/api/items";

const t = copy.card;

// 카드에는 칩 하나: 치명이면 빨간 띠, 문제가 있으면 주황 칩, 모르는 게 있으면 회색, 아니면 초록.
function Chip({ c }: { c: Card }) {
  const s = c.top_signal;
  if (s?.level === "fatal") return <div className="fatal">{s.title}</div>;
  if (s) return <span className="chip orange">◆ {s.title}</span>;
  if (c.unknown_count) return <span className="chip gray">● {t.unknown(c.unknown_count)}</span>;
  return <span className="chip green">● 확인 완료</span>;
}

// 공매는 출처 칩(테두리)만 — 상태 색(초록·회색·주황)과 섞지 않음. 확인 상태는 상세에서.
function SourceBadge({ c }: { c: Card }) {
  return <span className="chip gray f-none">{c.kind === "trust" ? t.trust : t.onbid}</span>;
}

function OnbidLine({ c }: { c: Card }) {
  if (c.top_signal) return <Chip c={c} />;
  if (c.next_round)
    return <div className="fs-xs fw-6">{t.nextRound(won(c.next_round.min_price_krw))}</div>;
  return <div className="sub m-0 fs-xs">{t.noNextRound}</div>;
}

// 카드 왼쪽(11/9 대표님 — 회색 네모에 글자만 있어 사진이 덜 뜬 것 같았음):
// 법원 사진이 있으면 사진, 없으면 종류마다 색 · 아이콘. 종류 판정은 API 규칙(usage_kind) 한 곳.
const KIND: Record<string, { label: string; d: string }> = {
  apt: {
    label: "아파트",
    d: "M5 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16M15 10h3a1 1 0 0 1 1 1v10M3 21h18M8 8h1M11 8h1M8 12h1M11 12h1M8 16h1M11 16h1",
  },
  villa: { label: "빌라", d: "M4 21V10l8-6 8 6v11M3 21h18M9 21v-5h6v5M8 12h2M14 12h2" },
  officetel: {
    label: "오피스텔",
    d: "M6 21V3h12v18M3 21h18M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2",
  },
  house: { label: "주택", d: "M3 11l9-7 9 7M5 9.5V21h14V9.5M10 21v-6h4v6" },
  shop: {
    label: "상가",
    d: "M4 9l1.5-5h13L20 9M4 9h16v2a2.5 2.5 0 0 1-5 0 2.5 2.5 0 0 1-5 0 2.5 2.5 0 0 1-5 0zM5 13v8h14v-8M10 21v-4h4v4",
  },
  land: { label: "토지", d: "M3 20h18M5 20l4-7 3 4 2-3 5 6M15 8a2 2 0 1 0 0-.01M15 10v3" },
};
const ETC = { label: "기타", d: "M4 7l8-4 8 4v10l-8 4-8-4zM4 7l8 4 8-4M12 11v10" };

function Thumb({ c }: { c: Card }) {
  const [broken, setBroken] = useState(false);
  const known = KIND[c.usage_kind ?? ""];
  const k = known ? (c.usage_kind as string) : "etc";
  const kind = known ?? ETC;
  if (c.photo && !broken)
    return (
      <div className="thumb photo">
        {/* eslint-disable-next-line @next/next/no-img-element -- 저장소 사진을 그대로(크기는 저장할 때 줄여 둠) */}
        <img src={c.photo} alt="" loading="lazy" decoding="async" onError={() => setBroken(true)} />
      </div>
    );
  return (
    <div className={`thumb kind k-${k}`} aria-label={kind.label} role="img">
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d={kind.d} />
      </svg>
      <span>{kind.label}</span>
    </div>
  );
}

// why: 모아 보기에서 이 물건이 그 모음에 든 이유 한 줄(있으면 「감정가보다 낮음」 줄 대신)
export function ItemCard({ c, why }: { c: Card; why?: string }) {
  const onbid = c.source === "onbid";
  return (
    <Link
      href={`/item/${encodeURIComponent(c.item_id)}`}
      className="card-go d-flex gap-12 py-12 px-0 c-inherit"
    >
      <Thumb c={c} />
      <div className="f-1 minw-0">
        <div className="sub d-flex jc-between gap-8 ai-center">
          <span className="ellipsis">
            <DDay d={c.d_day}>
              {onbid && !c.bid_end ? t.undecided : dday(c.d_day)}
              {onbid && c.bid_end ? ` ${t.closes}` : ""}
            </DDay>{" "}
            · {onbid ? c.case_no : `${c.court} ${c.case_no}`}
          </span>
          {onbid && <SourceBadge c={c} />}
        </div>
        <div className="fs-md fw-6 mt-2 ellipsis">
          {c.place} {c.building ?? c.usage} {c.area_m2 ? `${Math.round(c.area_m2)}㎡` : ""}
        </div>
        <div className="fs-lg fw-7 mt-2 ellipsis">
          {won(c.min_price_krw)}{" "}
          <span className="fs-xs fw-5 c-muted">
            {c.min_rate != null ? `${c.min_rate}%` : ""}
            {c.failed_count ? ` · ${t.failed(c.failed_count)}` : ""}
          </span>
        </div>
        <div className="mt-6">{onbid ? <OnbidLine c={c} /> : <Chip c={c} />}</div>
        {c.station && (
          <div className="fs-xs c-muted mt-4 ellipsis">
            {copy.walk.card(c.station.name, c.station.walk_min)}
          </div>
        )}
        {why && <div className="fs-xs fw-6 mt-6">{why}</div>}
        {!why && !onbid && c.below_appraisal_krw > 0 && (
          <div className="fs-xs fw-6 mt-6">{t.belowAppraisal(won(c.below_appraisal_krw))}</div>
        )}
      </div>
      <HeartButton id={c.item_id} />
    </Link>
  );
}
