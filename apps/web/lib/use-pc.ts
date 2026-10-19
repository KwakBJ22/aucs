"use client";

import { useEffect, useState } from "react";

// PC(1024px 이상)인지. 같은 화면을 휴대폰은 간결하게, PC는 전부 펼쳐 그릴 때 씁니다.
export function useIsPc(): boolean {
  const [pc, setPc] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(min-width: 1024px)");
    const on = () => setPc(m.matches);
    on();
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return pc;
}
