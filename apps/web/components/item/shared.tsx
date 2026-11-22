"use client";

import { createContext } from "react";
import type { DocKind, Question } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { useIsPc } from "@/lib/use-pc";

export const t = copy.item;

export const DOT: Record<Question["tone"], string> = {
  green: "var(--green)",
  gray: "var(--faint)",
  orange: "var(--amber)",
  red: "var(--red)",
  blue: "var(--blue)",
};

export const JUDGE_COLOR: Record<string, string> = {
  인수: "var(--red)",
  말소기준: "var(--blue)",
  "확인 필요": "var(--amber)",
};

// DOC-01 원문 보기: 화면 전체로 올라오는 창 (처음 열 때 한 번 불러옴)
export const DocCtx = createContext<(k: DocKind) => void>(() => {});

// 상세 PC 묶음 칸(11/22 디자인): 회색 판 · 머리 줄(이름 + 한 줄 요약 + 꼬리표) · 눌러 접고 폄.
// 휴대폰은 질문마다 이미 접히므로 묶음 칸 없이 내용만 그대로(예전 모양).
export function Panel({
  id,
  title,
  sum,
  tag,
  open = true,
  children,
}: {
  id?: string;
  title: string;
  sum?: React.ReactNode;
  tag?: React.ReactNode;
  open?: boolean;
  children: React.ReactNode;
}) {
  const pc = useIsPc();
  if (!pc) return <>{children}</>;
  return (
    <details id={id} className="q-panel" open={open}>
      <summary>
        <b>{title}</b>
        <span className="qp-sum">{sum}</span>
        {tag}
      </summary>
      <div className="qp-body">{children}</div>
    </details>
  );
}
