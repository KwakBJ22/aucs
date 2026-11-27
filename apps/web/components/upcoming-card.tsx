"use client";

import { KIND } from "./item-card";
import { HeartToggle } from "./heart-button";
import { copy } from "@/lib/copy.ko";
import { wonShort } from "@/lib/format";
import type { Upcoming } from "@/lib/api/items";

const t = copy.upcoming;
// 법원 목록 구분(01 토지 · 02 건물 · 03 집합건물) → 물건 카드와 같은 그림
const ICON: Record<string, string> = { 토지: "land", 건물: "house", 집합건물: "apt" };

// 곧 나올 물건 카드(11/27): 물건 카드(ItemCard)와 같은 틀 — 아직 상세가 없어 누르는 곳은 하트만
export function UpcomingCard({
  u,
  on,
  onToggle,
}: {
  u: Upcoming;
  on: boolean;
  onToggle: () => void;
}) {
  const k = ICON[u.kind] ?? "apt";
  const icon = KIND[k] ?? KIND.apt!;
  return (
    <div className="card-go d-flex gap-12">
      <div className={`thumb kind k-${k}`} aria-label={u.kind} role="img">
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
          <path d={icon.d} />
        </svg>
        <span>{u.kind}</span>
      </div>
      <div className="f-1 minw-0">
        <div className="sub ellipsis">
          {u.court} {u.case_no}
          {u.ordered_date ? ` · ${t.ordered(u.ordered_date)}` : ""}
        </div>
        <div className="ic-name ellipsis">{u.address}</div>
        {u.building && <div className="ic-note ellipsis">{u.building}</div>}
        {u.market.length > 0 && (
          <div className="ic-price ellipsis">
            {u.market.map((m) => `${m.area}㎡ ${wonShort(m.mid)}`).join(" · ")}{" "}
            <span className="ic-rate">{t.market}</span>
          </div>
        )}
        {u.expect && (
          <div className="ic-why">
            {u.expect.late ? t.late : t.expect(u.expect.from, u.expect.to)}
          </div>
        )}
      </div>
      <HeartToggle on={on} onToggle={onToggle} />
    </div>
  );
}
