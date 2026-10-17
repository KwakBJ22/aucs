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

export function ItemCard({ c }: { c: Card }) {
  const urgent = c.d_day != null && c.d_day <= 7;
  return (
    <div style={{ display: "flex", gap: 12, padding: "12px 0" }}>
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
        <div className="sub">
          <b style={{ color: urgent ? "var(--red)" : "var(--amber)" }}>{dday(c.d_day)}</b> ·{" "}
          {c.court} {c.case_no}
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
            {c.min_rate}%{c.failed_count ? ` · ${t.failed(c.failed_count)}` : ""}
          </span>
        </div>
        <div style={{ marginTop: 6 }}>
          <Chip c={c} />
        </div>
        {c.below_appraisal_krw > 0 && (
          <div style={{ fontSize: 12, color: "var(--blue)", marginTop: 6 }}>
            {t.belowAppraisal(won(c.below_appraisal_krw))}
          </div>
        )}
      </div>
    </div>
  );
}
