// 메뉴 목록은 이 파일 한 곳에만 둡니다. 휴대폰 하단 탭·PC 상단 메뉴·하위 메뉴가 모두 여기서 읽어요.

export type SubItem = { label: string; href: string };
export type NavItem = {
  key: string;
  label: string;
  href: string;
  group: "basic" | "pro";
  ready: boolean;
  match: string[]; // 이 주소로 시작하면 이 메뉴가 켜짐
  sub: SubItem[];
};

export const NAV: NavItem[] = [
  {
    key: "home",
    label: "홈",
    href: "/home",
    group: "basic",
    ready: true,
    match: ["/home", "/notifications", "/guide"],
    sub: [
      { label: "오늘 할 일", href: "/home" },
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
    sub: [
      { label: "조건으로 찾기", href: "/find" },
      { label: "표로 전부 보기", href: "/pro/items" },
    ],
  },
  {
    key: "watch",
    label: "관심",
    href: "/watch",
    group: "basic",
    ready: true,
    match: ["/watch"],
    sub: [
      { label: "관심 물건", href: "/watch" },
      { label: "비교함", href: "/compare" },
      { label: "물건 알림", href: "/notifications" },
    ],
  },
  {
    key: "me",
    label: "내 경매",
    href: "/me",
    group: "basic",
    ready: true,
    match: ["/me"],
    sub: [{ label: "모의입찰과 복기", href: "/me" }],
  },
  {
    key: "pro-items",
    label: "전체 물건",
    href: "/pro/items",
    group: "pro",
    ready: true,
    match: ["/pro/items"],
    sub: [{ label: "표 보기", href: "/pro/items" }],
  },
  {
    key: "pro-map",
    label: "지도 분석",
    href: "/pro/map",
    group: "pro",
    ready: false,
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
    sub: [{ label: "비교 중과 뺀 물건", href: "/compare" }],
  },
  {
    key: "pro-cases",
    label: "사건·문건",
    href: "/pro/cases",
    group: "pro",
    ready: true,
    match: ["/pro/cases"],
    sub: [{ label: "사건 목록과 문건 흐름", href: "/pro/cases" }],
  },
  {
    key: "pro-market",
    label: "시장 분석",
    href: "/pro/market",
    group: "pro",
    ready: true,
    match: ["/pro/market"],
    sub: [
      { label: "지역 시장", href: "/pro/market#region" },
      { label: "낙찰 사례", href: "/pro/market#cases" },
      { label: "성적표", href: "/pro/market#score" },
    ],
  },
];

// 휴대폰 하단 탭 5개 (찾고 → 담고 → 입찰하고 → 낙찰 뒤 → 전체)
export const TABS = [
  { key: "home", label: "홈", href: "/home", match: ["/home", "/notifications", "/guide"] },
  { key: "find", label: "찾기", href: "/find", match: ["/find", "/item"] },
  { key: "watch", label: "관심", href: "/watch", match: ["/watch", "/compare"] },
  { key: "me", label: "내 경매", href: "/me", match: ["/me"] },
  { key: "more", label: "내 정보", href: "/more", match: ["/more", "/pro", "/plans"] },
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
