"use client";

import { useState } from "react";
import type { ItemDetail } from "@/lib/api/items";
import { t } from "@/components/item/shared";

// 휴대폰: 실패 사례 11가지 중 걸린 것만, 나머지는 한 줄로 접음
export function FailMobile({ rows }: { rows: NonNullable<ItemDetail["failure_table"]> }) {
  const [open, setOpen] = useState(false);
  const hit = rows.filter((r) => r.state === "걸림");
  const count: Record<string, number> = {};
  rows.forEach((r) => (count[r.state] = (count[r.state] ?? 0) + 1));
  return (
    <div className="m-block mt-10">
      <div className="fs-md fw-7">{t.failHead(rows.length, hit.length)}</div>
      {hit.map((r) => (
        <div key={r.code} className="fs-md py-6 px-0 c-red">
          ◆ {r.title}
          <span className="sub d-block">{r.why}</span>
        </div>
      ))}
      <button className="cond-row bg-bg mt-6" onClick={() => setOpen(!open)}>
        <span className="fs-md">{t.failFold(count)}</span>
        <span className="sub">{open ? "▴" : "›"}</span>
      </button>
      {open &&
        rows
          .filter((r) => r.state !== "걸림")
          .map((r) => (
            <div key={r.code} className="line-row fs-sm">
              <span className="minw-0">
                {r.title}
                {r.why && <span className="sub d-block fs-xs">{r.why}</span>}
              </span>
              <span className="nowrap" style={{ color: t.failColor[r.state] }}>
                {r.state}
              </span>
            </div>
          ))}
      <div className="sub fs-xs">{t.failureTableNote}</div>
    </div>
  );
}
