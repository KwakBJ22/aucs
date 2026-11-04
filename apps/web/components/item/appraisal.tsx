"use client";

import { useState } from "react";
import type { ItemDetail } from "@/lib/api/items";
import { t } from "@/components/item/shared";

// 감정평가 요점(11/4 대표님 — 개인정보 가리고 사용 허락, 평가사 이름을 곁에 붙임). 처음엔 세 칸만, 누르면 전부
export function AppraisalPoints({ a }: { a: NonNullable<ItemDetail["appraisal"]> }) {
  const [open, setOpen] = useState(false);
  const c = t.appraisal;
  const rows = open ? a.points : a.points.slice(0, 3);
  return (
    <div className="m-block mt-10">
      <div className="fs-md fw-7">
        {c.head}
        <span className="sub fw-4">
          {" "}
          · {a.firm ?? c.source}
          {a.price_date && ` · ${c.asOf(a.price_date)}`}
        </span>
      </div>
      {rows.map((p) => (
        <div key={p.label} className="py-6 px-0 fs-sm">
          <b>{p.label}</b>
          <span className="sub d-block m-0">{p.text}</span>
        </div>
      ))}
      {a.points.length > 3 && (
        <button className="cond-row bg-bg mt-6" onClick={() => setOpen(!open)}>
          <span className="fs-md">{open ? c.less : c.more(a.points.length - 3)}</span>
          <span className="sub">{open ? "▴" : "›"}</span>
        </button>
      )}
    </div>
  );
}
