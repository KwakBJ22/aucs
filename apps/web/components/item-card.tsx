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
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: "1px 6px",
        borderRadius: 5,
        border: "1px solid var(--text)",
        flexShrink: 0,
      }}
    >
      {c.kind === "trust" ? t.trust : t.onbid}
    </span>
  );
}

function OnbidLine({ c }: { c: Card }) {
  if (c.top_signal) return <Chip c={c} />;
  if (c.next_round)
    return (
      <div style={{ fontSize: 12, color: "var(--blue)" }}>
        {t.nextRound(won(c.next_round.min_price_krw))}
      </div>
    );
  return (
    <div className="sub" style={{ margin: 0, fontSize: 12 }}>
      {t.noNextRound}
    </div>
  );
}

export function ItemCard({ c }: { c: Card }) {
  const urgent = c.d_day != null && c.d_day <= 7;
  const onbid = c.source === "onbid";
  return (
    <Link
      href={`/item/${encodeURIComponent(c.item_id)}`}
      style={{ display: "flex", gap: 12, padding: "12px 0", color: "inherit" }}
    >
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: 12,
          background: "var(--gray-chip)",
          flexShrink: 0,
        }}
      />
      <div style={{ flexGrow: 1, minWidth: 0 }}>
        <div
          className="sub"
          style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}
        >
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            <b style={{ color: urgent ? "var(--red)" : "var(--amber)" }}>
              {onbid && !c.bid_end ? t.undecided : dday(c.d_day)}
              {onbid && c.bid_end ? ` ${t.closes}` : ""}
            </b>{" "}
            · {onbid ? c.case_no : `${c.court} ${c.case_no}`}
          </span>
          {onbid && <SourceBadge c={c} />}
        </div>
        <div
          style={{
            fontSize: 14,
            fontWeight: 600,
            marginTop: 2,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {c.place} {c.building ?? c.usage} {c.area_m2 ? `${Math.round(c.area_m2)}㎡` : ""}
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>
          {won(c.min_price_krw)}{" "}
          <span style={{ fontSize: 12, fontWeight: 500, color: "var(--muted)" }}>
            {c.min_rate != null ? `${c.min_rate}%` : ""}
            {c.failed_count ? ` · ${t.failed(c.failed_count)}` : ""}
          </span>
        </div>
        <div style={{ marginTop: 6 }}>{onbid ? <OnbidLine c={c} /> : <Chip c={c} />}</div>
        {!onbid && c.below_appraisal_krw > 0 && (
          <div style={{ fontSize: 12, color: "var(--blue)", marginTop: 6 }}>
            {t.belowAppraisal(won(c.below_appraisal_krw))}
          </div>
        )}
      </div>
      <HeartButton id={c.item_id} />
    </Link>
  );
}
