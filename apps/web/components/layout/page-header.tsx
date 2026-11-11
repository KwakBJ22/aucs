"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

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
  const path = usePathname();
  // 첫 화면들(뒤로 없음)은 오른쪽 끝에 「내 정보」 — 아래 탭 다섯째 칸을 포인트 벌기에 내줌(11/12 대표님)
  const menu =
    !back && !path.startsWith("/more") ? (
      <Link href="/more" aria-label="내 정보" className="icon-btn m-only d-flex jc-end">
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          aria-hidden="true"
        >
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </Link>
    ) : null;
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
          <button aria-label="뒤로" className="tb-back " onClick={() => router.back()}>
            {arrow}
          </button>
        ) : back ? (
          <Link href={back} aria-label="뒤로" className="tb-back">
            {arrow}
          </Link>
        ) : null}
        {title ? <h1 className="brand">{title}</h1> : null}
        <span className="f-1" />
        {right || menu ? (
          <span className="d-flex ai-center gap-8">
            {right}
            {menu}
          </span>
        ) : null}
      </div>
      {sub && <div className="tb-sub sub">{sub}</div>}
    </>
  );
}
