import type { CollectionKey } from "@/lib/copy.ko";

// 모아 보기 모음마다 그림 하나(11/11 대표님) — 선 그림, 색은 글자색을 따름
const PATHS: Record<CollectionKey, string> = {
  // 값표 + 아래 화살표: 시세보다 싸게
  cheap:
    "M3 12.5V5a2 2 0 0 1 2-2h7.5L21 11.5 12.5 20 3 12.5Z M7.5 7.5h.01 M12 10v6 M9.5 13.5 12 16l2.5-2.5",
  // 방패 + 체크: 떠안는 돈 없음
  safe: "M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6L12 3Z M8.8 12.2l2.2 2.2 4.4-4.6",
  // 오르는 선: 감정 뒤 값이 오름
  rising: "M3 17l6-6 4 4 8-8 M15 7h6v6",
  // 시계: 기다리면 더 싸짐
  next: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M12 7v5l3.5 2",
  // 전철: 역 가까움
  station:
    "M7 3h10a2 2 0 0 1 2 2v9a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V5a2 2 0 0 1 2-2Z M5 10h14 M8.5 13.5h.01 M15.5 13.5h.01 M8 17l-2 4 M16 17l2 4",
  // 느낌표 세모: 특수 권리
  special: "M12 4 2.8 19.5h18.4L12 4Z M12 10v4.5 M12 17h.01",
};

export function CollectionIcon({ k }: { k: CollectionKey }) {
  return (
    <span className="col-ico" aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        width="22"
        height="22"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d={PATHS[k]} />
      </svg>
    </span>
  );
}
