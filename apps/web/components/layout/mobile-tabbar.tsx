"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TABS, activeTab } from "@/lib/nav";

const ICON: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
  find: "M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm9 16-3.5-3.5",
  watch: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
  me: "M7 4h10a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm2 6h6m-6 4h6",
  more: "M4 6h16M4 12h16M4 18h16",
};

// 휴대폰 바닥: 하단 탭 5개. PC에서는 CSS로 숨김.
export function MobileTabbar() {
  const on = activeTab(usePathname());
  return (
    <nav className="tabbar" aria-label="하단 탭">
      {TABS.map((t) => (
        <Link key={t.key} href={t.href} className={on === t.key ? "on" : ""}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d={ICON[t.key]} />
          </svg>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
