"use client";

import { createContext } from "react";
import type { DocKind, Question } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";

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
