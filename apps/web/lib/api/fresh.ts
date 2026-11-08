"use client";

import { useEffect, useState } from "react";
import { FRESH_EVENT } from "./client";

// 지난번 자료를 먼저 그린 화면이, 새 자료가 오면 조용히 다시 부르게 하는 숫자(11/8).
// 화면의 자료 부르는 useEffect 의존 목록에 넣음 — 다시 부르면 이미 받아 둔 새 자료라 바로 그려짐.
export function useFresh(): number {
  const [n, setN] = useState(0);
  useEffect(() => {
    const up = () => setN((x) => x + 1);
    window.addEventListener(FRESH_EVENT, up);
    return () => window.removeEventListener(FRESH_EVENT, up);
  }, []);
  return n;
}
