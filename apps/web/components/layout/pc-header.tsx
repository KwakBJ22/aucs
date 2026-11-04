"use client";

import { Logo } from "@/components/logo";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { NAV, activeNav } from "@/lib/nav";

const Lock = () => (
  <svg
    width="13"
    height="13"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    aria-hidden="true"
  >
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </svg>
);

// PC 머리: 1줄 = 옥스 · 기본 메뉴 | 전문가 메뉴 · 찾기 칸 · 알림 · 내 정보, 2줄 = 고른 메뉴의 하위 항목.
// 휴대폰에서는 CSS로 숨기고 하단 탭을 씁니다.
export function PcHeader({ admin = false }: { admin?: boolean }) {
  const path = usePathname();
  const router = useRouter();
  const { session } = useSession();
  const [q, setQ] = useState("");
  const cur = admin ? undefined : activeNav(path);
  const guest = !session;
  const subOn = cur?.sub.findIndex((x) => x.href.split("#")[0] === path) ?? -1;

  function search(e: React.FormEvent) {
    e.preventDefault();
    const v = q.trim();
    // 사건번호는 찾기로(끝난 사건도 결과·상세로 바로 감, 11/1), 주소·단지는 전체 물건 표로
    if (v)
      router.push(
        /\d{4}\s*타경\s*\d+|^\d{4}-\d{4,5}-\d{3}$/.test(v)
          ? `/find?q=${encodeURIComponent(v)}`
          : `/pro/items?q=${encodeURIComponent(v)}`,
      );
  }

  return (
    <header className="pc-header">
      <div className="ph-top">
        <Link href="/home" className="ph-brand" aria-label={copy.appName}>
          <Logo size="sm" />
        </Link>
        {admin ? (
          <>
            <span className="ph-admin">관리자</span>
            <Link href="/home" className="ph-back">
              서비스 화면으로 ›
            </Link>
          </>
        ) : (
          <>
            <nav aria-label="기본 메뉴" className="ph-menu">
              {NAV.filter((n) => n.group === "basic").map((n) => (
                <Link key={n.key} href={n.href} className={cur?.key === n.key ? "on" : ""}>
                  {n.label}
                </Link>
              ))}
            </nav>
            <span className="ph-bar" aria-hidden="true" />
            <nav aria-label="전문가 메뉴" className="ph-menu">
              {NAV.filter((n) => n.group === "pro").map((n) =>
                !n.ready ? (
                  <span key={n.key} className="off" title="준비 중">
                    {n.label}
                    <small>준비 중</small>
                  </span>
                ) : guest ? (
                  <Link key={n.key} href="/login" className="locked">
                    <Lock />
                    {n.label}
                  </Link>
                ) : (
                  <Link key={n.key} href={n.href} className={cur?.key === n.key ? "on" : ""}>
                    {n.label}
                  </Link>
                ),
              )}
            </nav>
          </>
        )}
        <span className="f-1" />
        {!admin && (
          <form onSubmit={search} className="ph-search" role="search">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input
              aria-label="사건번호나 주소로 찾기"
              placeholder="사건번호·주소로 찾기"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </form>
        )}
        {!admin && !guest && (
          <Link href="/notifications" aria-label={copy.noti.title} className="ph-icon">
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              aria-hidden="true"
            >
              <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" />
              <path d="M10 20a2 2 0 0 0 4 0" />
            </svg>
          </Link>
        )}
        {!admin &&
          (guest ? (
            <Link href="/login" className="ph-kakao">
              {copy.home.kakao}
            </Link>
          ) : (
            <Link href="/more" className="ph-me">
              <span className="ph-avatar">나</span>내 정보
            </Link>
          ))}
      </div>
      {cur && cur.sub.length > 0 && (
        <nav aria-label="하위 메뉴" className="ph-sub">
          {cur.sub.map((s, i) => (
            <Link key={s.href + i} href={s.href} className={i === subOn ? "on" : ""}>
              {s.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
