import Link from "next/link";
import { HeartButton } from "./heart-button";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
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
  return (
    <span className="fs-xs fw-6 py-0 px-6 r-4 b-0 bg-gray-chip f-none">
      {c.kind === "trust" ? t.trust : t.onbid}
    </span>
  );
}

function OnbidLine({ c }: { c: Card }) {
  if (c.top_signal) return <Chip c={c} />;
  if (c.next_round)
    return <div className="fs-xs c-blue">{t.nextRound(won(c.next_round.min_price_krw))}</div>;
  return <div className="sub m-0 fs-xs">{t.noNextRound}</div>;
}

export function ItemCard({ c }: { c: Card }) {
  const urgent = c.d_day != null && c.d_day <= 7;
  const onbid = c.source === "onbid";
  return (
    <Link
      href={`/item/${encodeURIComponent(c.item_id)}`}
      className="d-flex gap-12 py-12 px-0 c-inherit"
    >
      <div className="r-12 bg-gray-chip f-none" style={{ width: 72, height: 72 }} />
      <div className="f-1 minw-0">
        <div className="sub d-flex jc-between gap-8 ai-center">
          <span className="nowrap" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
            <b style={{ color: urgent ? "var(--red)" : "var(--amber)" }}>
              {onbid && !c.bid_end ? t.undecided : dday(c.d_day)}
              {onbid && c.bid_end ? ` ${t.closes}` : ""}
            </b>{" "}
            · {onbid ? c.case_no : `${c.court} ${c.case_no}`}
          </span>
          {onbid && <SourceBadge c={c} />}
        </div>
        <div
          className="fs-md fw-6 mt-2 nowrap"
          style={{ overflow: "hidden", textOverflow: "ellipsis" }}
        >
          {c.place} {c.building ?? c.usage} {c.area_m2 ? `${Math.round(c.area_m2)}㎡` : ""}
        </div>
        <div className="fs-lg fw-7 mt-2">
          {won(c.min_price_krw)}{" "}
          <span className="fs-xs fw-5 c-muted">
            {c.min_rate != null ? `${c.min_rate}%` : ""}
            {c.failed_count ? ` · ${t.failed(c.failed_count)}` : ""}
          </span>
        </div>
        <div className="mt-6">{onbid ? <OnbidLine c={c} /> : <Chip c={c} />}</div>
        {!onbid && c.below_appraisal_krw > 0 && (
          <div className="fs-xs c-blue mt-6">{t.belowAppraisal(won(c.below_appraisal_krw))}</div>
        )}
      </div>
      <HeartButton id={c.item_id} />
    </Link>
  );
}
