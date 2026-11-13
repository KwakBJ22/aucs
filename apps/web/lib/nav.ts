// 메뉴 목록은 이 파일 한 곳에만 둡니다. 휴대폰 하단 탭·PC 상단 메뉴·하위 메뉴가 모두 여기서 읽어요.

export type SubItem = { label: string; href: string };
export type NavItem = {
  key: string;
  label: string;
  href: string;
  group: "basic" | "pro";
  ready: boolean;
  match: string[]; // 이 주소로 시작하면 이 메뉴가 켜짐
  pcHide?: boolean; // PC 머리 메뉴에서 뺌(홈은 로고를 누르면 가므로, 11/4)
  // 하위 메뉴: 같은 메뉴 안의 화면·자리만, 두 개 이상일 때만 줄을 보임(11/7 — 다른 메뉴로 넘어가는 항목 뺌)
  sub: SubItem[];
};

export const NAV: NavItem[] = [
  {
    key: "home",
    label: "홈",
    href: "/home",
    group: "basic",
    ready: true,
    match: ["/home", "/notifications", "/guide", "/collections"],
    pcHide: true,
    sub: [
      { label: "오늘의 추천", href: "/home" },
      { label: "모아 보기", href: "/collections" },
      { label: "알림함", href: "/notifications" },
      { label: "경매 처음이세요?", href: "/guide" },
    ],
  },
  {
    key: "find",
    label: "찾기",
    href: "/find",
    group: "basic",
    ready: true,
    match: ["/find", "/item"],
    sub: [],
  },
  {
    key: "watch",
    label: "관심",
    href: "/watch",
    group: "basic",
    ready: true,
    match: ["/watch"],
    sub: [],
  },
  {
    key: "me",
    label: "내 경매",
    href: "/me",
    group: "basic",
    ready: true,
    match: ["/me"],
    sub: [],
  },
  {
    key: "points",
    label: "포인트 UP!",
    href: "/points",
    group: "basic",
    ready: true,
    match: ["/points"],
    sub: [],
  },
  {
    key: "pro-items",
    label: "전체 물건",
    href: "/pro/items",
    group: "pro",
    ready: true,
    match: ["/pro/items"],
    sub: [],
  },
  {
    key: "pro-map",
    label: "지도 분석",
    href: "/pro/map",
    group: "pro",
    ready: true,
    match: ["/pro/map"],
    sub: [],
  },
  {
    key: "compare",
    label: "비교함",
    href: "/compare",
    group: "pro",
    ready: true,
    match: ["/compare"],
    sub: [],
  },
  {
    key: "pro-cases",
    label: "사건·문건",
    href: "/pro/cases",
    group: "pro",
    ready: true,
    match: ["/pro/cases"],
    sub: [],
  },
  {
    key: "pro-market",
    label: "시장 분석",
    href: "/pro/market",
    group: "pro",
    ready: true,
    match: ["/pro/market"],
    sub: [
      { label: "성적표", href: "/pro/market#score" },
      { label: "지역 시장", href: "/pro/market#region" },
      { label: "낙찰 사례", href: "/pro/market#cases" },
    ],
  },
];

// 휴대폰 하단 탭 5개 (찾고 → 담고 → 입찰하고 → 서류 채우기). 내 정보는 화면 머리 오른쪽 끝(11/12)
export const TABS = [
  {
    key: "home",
    label: "홈",
    href: "/home",
    match: ["/home", "/notifications", "/guide", "/collections"],
  },
  { key: "find", label: "찾기", href: "/find", match: ["/find", "/item", "/pro/map"] },
  { key: "watch", label: "관심", href: "/watch", match: ["/watch", "/compare"] },
  { key: "me", label: "내 경매", href: "/me", match: ["/me"] },
  { key: "points", label: "포인트", href: "/points", match: ["/points"] },
] as const;

export function activeNav(path: string): NavItem | undefined {
  // 더 긴(구체적인) 주소가 먼저 맞도록
  let best: NavItem | undefined;
  let len = -1;
  for (const n of NAV)
    for (const m of n.match)
      if (path.startsWith(m) && m.length > len) {
        best = n;
        len = m.length;
      }
  return best;
}

export function activeTab(path: string): string {
  for (const t of TABS) if (t.match.some((m) => path.startsWith(m))) return t.key;
  return "";
}
