"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

// 화면 머리(제목 줄). 휴대폰: 뒤로 · 제목 · 오른쪽 단추 하나. PC: 같은 자리가 화면 제목이 됩니다.
// back="history" 는 바로 앞 화면으로(브라우저 뒤로).
export function PageHeader({
  title,
  back,
  right,
  sub,
}: {
  title: React.ReactNode;
  back?: string;
  right?: React.ReactNode;
  sub?: React.ReactNode;
}) {
  const router = useRouter();
  const arrow = (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <path d="m15 5-7 7 7 7" />
    </svg>
  );
  return (
    <>
      <div className="topbar">
        {back === "history" ? (
          <button aria-label="뒤로" className="tb-back b-0 bg-none" onClick={() => router.back()}>
            {arrow}
          </button>
        ) : back ? (
          <Link href={back} aria-label="뒤로" className="tb-back">
            {arrow}
          </Link>
        ) : null}
        {title ? <h1 className="brand">{title}</h1> : null}
        <span className="f-1" />
        {right}
      </div>
      {sub && <div className="tb-sub sub">{sub}</div>}
    </>
  );
}
