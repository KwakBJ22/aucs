"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { copy } from "@/lib/copy.ko";
import { setMode, useMode } from "@/lib/mode";
import { modeOfPath } from "@/lib/nav";

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
  const saved = useMode();
  const mode = modeOfPath(path) ?? saved;
  // 전문가 탭 화면(비교함 · 지도 분석)은 휴대폰에선 탭 첫 화면 — 뒤로 대신 「기본으로」 · ☰(PC는 뒤로 그대로)
  const first = !back || modeOfPath(path) === "pro";
  // 첫 화면들(뒤로 없음)은 오른쪽 끝에 「내 정보」 — 아래 탭 다섯째 칸을 포인트 벌기에 내줌(11/12 대표님)
  const menu =
    first && !path.startsWith("/more") ? (
      <Link href="/more" aria-label="내 정보" className="icon-btn m-only d-flex jc-end">
        <svg
          width="26"
          height="26"
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
  // 휴대폰 첫 화면들 머리: 「전문가로」 ↔ 「기본으로」 — 누르면 아래 탭이 통째로 바뀜(11/17 대표님). PC는 머리 메뉴.
  const toggle = first ? (
    <button
      type="button"
      className="btn sm soft tb-pro m-only"
      onClick={() => {
        const next = mode === "pro" ? "basic" : "pro";
        setMode(next);
        router.push(next === "pro" ? "/pro/map" : "/home"); // 전문가 첫 메뉴(11/17)
      }}
    >
      {mode === "pro" ? copy.mode.toBasic : copy.mode.toPro}
    </button>
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
          <button
            aria-label="뒤로"
            className={`tb-back ${back && first ? "pc-back" : ""}`}
            onClick={() => router.back()}
          >
            {arrow}
          </button>
        ) : back ? (
          <Link href={back} aria-label="뒤로" className={`tb-back ${first ? "pc-back" : ""}`}>
            {arrow}
          </Link>
        ) : null}
        {title ? <h1 className="brand">{title}</h1> : null}
        <span className="f-1" />
        {right || menu || toggle ? (
          <span className={`d-flex ai-center ${menu ? "tb-tools" : "gap-8"}`}>
            {toggle}
            {right}
            {menu}
          </span>
        ) : null}
      </div>
      {sub && <div className="tb-sub sub">{sub}</div>}
    </>
  );
}
