"use client";

import { useSyncExternalStore } from "react";

// PC(1024px 이상)인지. 같은 화면을 휴대폰은 간결하게, PC는 전부 펼쳐 그릴 때 씁니다.
// 10/27: 화면 안에서 옮겨 다닐 때는 처음부터 맞는 값으로 그림(예전엔 휴대폰으로 한 번 그린 뒤 PC로 다시 그려
// PC에서만 부르는 자료가 늦게 출발했음). 창 크기 감시도 부품마다가 아니라 하나만 둠.
const QUERY = "(min-width: 1024px)";
let mql: MediaQueryList | null = null;
const media = () => (mql ??= window.matchMedia(QUERY));

function subscribe(cb: () => void): () => void {
  const m = media();
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}

export function useIsPc(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => media().matches,
    () => false,
  );
}
