"use client";

import { useEffect, useState, type ReactNode } from "react";

// 스켈레톤(11/4): 자료를 기다리는 동안 화면 모양 그대로 연한 판을 깔아 둠.
// 0.3초 안에 자료가 오면 아무것도 띄우지 않음(빠른 화면이 깜빡이지 않게). 모양은 styles/parts.css .sk*

const WAIT_MS = 300;

/** 0.3초 기다렸다가 보여 줌 — 금방 오는 자료에 스켈레톤이 번쩍이지 않게. */
export function Delayed({ children, ms = WAIT_MS }: { children: ReactNode; ms?: number }) {
  const [on, setOn] = useState(ms <= 0);
  useEffect(() => {
    if (ms <= 0) return;
    const id = window.setTimeout(() => setOn(true), ms);
    return () => window.clearTimeout(id);
  }, [ms]);
  if (!on) return null;
  return (
    <div className="sk-wrap" aria-busy="true" aria-live="polite">
      {children}
    </div>
  );
}

/** 판 하나. 폭·높이는 그 자리마다 다른 값이라 인자로. */
export function Sk({
  w = "100%",
  h,
  className = "",
}: {
  w?: number | string;
  h?: number;
  className?: string;
}) {
  return <span className={`sk ${className}`} style={{ width: w, height: h }} />;
}

/** 글 줄 여러 개(마지막 줄은 짧게). */
export function SkLines({ n = 3, gap = 10 }: { n?: number; gap?: number }) {
  return (
    <div className="d-flex f-col" style={{ gap }}>
      {Array.from({ length: n }, (_, i) => (
        <Sk key={i} className="sk-line" w={i === n - 1 ? "55%" : "100%"} />
      ))}
    </div>
  );
}

/** 물건 카드 모양(왼쪽 판 + 네 줄) — 홈·찾기·관심 목록. */
export function SkCard() {
  return (
    <div className="d-flex gap-12 py-12 px-0">
      <Sk className="sk-thumb" />
      <div className="f-1 minw-0 d-flex f-col gap-8">
        <Sk className="sk-line" w="45%" h={12} />
        <Sk className="sk-line" w="80%" />
        <Sk className="sk-line" w="38%" h={18} />
        <Sk className="sk-line" w="28%" h={12} />
      </div>
    </div>
  );
}

export function SkCards({ n = 5, grid = false }: { n?: number; grid?: boolean }) {
  return (
    <div className={grid ? "card-grid" : ""}>
      {Array.from({ length: n }, (_, i) => (
        <SkCard key={i} />
      ))}
    </div>
  );
}

/** 목록 줄 모양(두 줄 글 + 오른쪽 작은 판) — 알림·메뉴·관리자 목록. */
export function SkRows({ n = 5, icon = false }: { n?: number; icon?: boolean }) {
  return (
    <div>
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="d-flex ai-center gap-12 mh-56 py-12 px-0">
          {icon && <Sk className="sk-thumb" />}
          <div className="f-1 minw-0 d-flex f-col gap-8">
            <Sk className="sk-line" w={i % 2 ? "62%" : "78%"} />
            <Sk className="sk-line" w="40%" h={11} />
          </div>
          <Sk className="sk-line" w={36} h={12} />
        </div>
      ))}
    </div>
  );
}

/** 구역 하나(소제목 + 줄) — 화면 안 카드 묶음. */
export function SkSection({ rows = 3, cards = false }: { rows?: number; cards?: boolean }) {
  return (
    <section className="section">
      <Sk className="sk-line mb-12" w="35%" h={18} />
      {cards ? <SkCards n={rows} /> : <SkRows n={rows} />}
    </section>
  );
}

/** 화면 머리(제목 + 아랫줄). */
export function SkHeader() {
  return (
    <div className="d-flex f-col gap-8 pt-12 pb-12 px-0">
      <Sk className="sk-title" w="52%" />
      <Sk className="sk-line" w="70%" h={12} />
    </div>
  );
}

/** 목록 화면 한 장(머리 + 카드). */
export function SkListPage({ n = 5, cards = true }: { n?: number; cards?: boolean }) {
  return (
    <Delayed>
      <SkHeader />
      <section className="section">{cards ? <SkCards n={n} /> : <SkRows n={n} />}</section>
    </Delayed>
  );
}

/** 물건 상세 모양(사진 자리 · 제목 두 줄 · 금액 판 · 카드 묶음). */
export function SkDetail() {
  return (
    <Delayed>
      <Sk className="sk-box mt-8" h={200} />
      <div className="d-flex f-col gap-10 pt-12 pb-12 px-0">
        <Sk className="sk-line" w="40%" h={12} />
        <Sk className="sk-title" w="85%" />
        <Sk className="sk-title" w="60%" />
      </div>
      <section className="section">
        <div className="d-flex f-col gap-12">
          {[0, 1, 2].map((i) => (
            <div key={i} className="d-flex jc-between">
              <Sk className="sk-line" w="30%" />
              <Sk className="sk-line" w="34%" h={18} />
            </div>
          ))}
        </div>
      </section>
      <SkSection rows={3} />
    </Delayed>
  );
}

/** 표 모양(PC 전문가·관리자) — 선 대신 줄무늬처럼 판을 번갈아. */
export function SkTable({ rows = 10, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="d-flex f-col gap-6">
      <div className="d-flex gap-12 py-8 px-8">
        {Array.from({ length: cols }, (_, j) => (
          <Sk key={j} className="sk-line f-1" h={12} />
        ))}
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="d-flex gap-12 py-10 px-8">
          {Array.from({ length: cols }, (_, j) => (
            <Sk key={j} className="sk-line f-1" w={j === 0 ? "100%" : undefined} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** 이름 칩 자리(지역 고르기 등). */
export function SkChips({ n = 12 }: { n?: number }) {
  const ws = [64, 78, 56, 70, 84, 60];
  return (
    <div className="d-flex f-wrap gap-8">
      {Array.from({ length: n }, (_, i) => (
        <Sk key={i} className="sk-chip" w={ws[i % ws.length]} />
      ))}
    </div>
  );
}
