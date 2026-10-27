"use client";

import { useState } from "react";
import type { ItemDetail } from "@/lib/api/items";
import { t } from "@/components/item/shared";

// 휴대폰: 실패 사례 11가지 중 걸린 것만, 나머지는 한 줄로 접음
export function FailMobile({ rows }: { rows: NonNullable<ItemDetail["failure_table"]> }) {
  const [open, setOpen] = useState(false);
  const hit = rows.filter((r) => r.state === "걸림");
  const need = rows.filter((r) => r.state === "확인 필요").length;
  const none = rows.filter((r) => r.state === "신호 없음").length;
  return (
    <div className="m-block" style={{ marginTop: 10 }}>
      <div style={{ fontSize: 14, fontWeight: 700 }}>{t.failHead(rows.length, hit.length)}</div>
      {hit.map((r) => (
        <div key={r.code} style={{ fontSize: 14, padding: "6px 0", color: "var(--red)" }}>
          ◆ {r.title}
          <span className="sub" style={{ display: "block" }}>
            {r.why}
          </span>
        </div>
      ))}
      <button
        className="cond-row"
        style={{ background: "var(--bg)", marginTop: 6 }}
        onClick={() => setOpen(!open)}
      >
        <span style={{ fontSize: 14 }}>{t.failFold(none, need)}</span>
        <span className="sub">{open ? "▴" : "›"}</span>
      </button>
      {open &&
        rows
          .filter((r) => r.state !== "걸림")
          .map((r) => (
            <div key={r.code} className="line-row" style={{ fontSize: 13 }}>
              <span>{r.title}</span>
              <span
                style={{
                  color: r.state === "확인 필요" ? "var(--orange)" : "var(--faint)",
                  whiteSpace: "nowrap",
                }}
              >
                {r.state}
              </span>
            </div>
          ))}
      <div className="sub" style={{ fontSize: 12 }}>
        {t.failureTableNote}
      </div>
    </div>
  );
}
