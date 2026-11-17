"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { setMode, useMode } from "@/lib/mode";
import { PRO_TABS, TABS, activeTab, modeOfPath, type Tab } from "@/lib/nav";
import { toTop } from "@/lib/scroll";

const ICON: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
  find: "M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm9 16-3.5-3.5",
  watch: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
  me: "M7 4h10a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm2 6h6m-6 4h6",
  points: "M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zm-2.5 5h3.2a2.3 2.3 0 0 1 0 4.6H9.5M9.5 8v8",
  // 전문가 탭(11/17)
  "pro-items": "M4 5h16M4 10h16M4 15h16M4 20h16",
  "pro-map": "M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zm0 0v14m6-12v14",
  compare: "M4 5h7v14H4zm9 0h7v14h-7z",
  "pro-cases": "M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm7 0v5h5M9 13h6m-6 4h6",
  "pro-market": "M4 20V10m6 10V4m6 16v-7m4 7H3",
};

// 휴대폰 바닥: 하단 탭 5개 — 기본 / 전문가(머리의 「전문가로」 · 「기본으로」, 11/17). PC에서는 CSS로 숨김.
export function MobileTabbar() {
  const path = usePathname();
  const mode = useMode();
  // 전문가 화면에 들어오면 전문가 탭, 기본 탭 화면에 들어오면 기본 탭(물건 화면 등은 그대로)
  useEffect(() => {
    const m = modeOfPath(path);
    if (m) setMode(m);
  }, [path]);
  const tabs: readonly Tab[] = (modeOfPath(path) ?? mode) === "pro" ? PRO_TABS : TABS;
  const on = activeTab(path, tabs);
  return (
    <nav className="tabbar" aria-label="하단 탭">
      {tabs.map((t) => (
        <Link
          key={t.key}
          href={t.href}
          className={on === t.key ? "on" : ""}
          onClick={(e) => {
            if (on === t.key && window.location.pathname === t.href) {
              e.preventDefault(); // 지금 탭을 또 누르면 맨 위로
              toTop();
            }
          }}
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            aria-hidden="true"
          >
            <path d={ICON[t.key]} />
          </svg>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
