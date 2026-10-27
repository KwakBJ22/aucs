import { ApiError, apiBaseUrl, clearMeCache, getMine } from "./client";
import type { Calc, ItemCard, ItemDetail, Schedule } from "./items";

export type WatchStep = "found" | "review" | "field" | "money" | "bid" | "result" | "after";
export const WATCH_STEPS: WatchStep[] = [
  "found",
  "review",
  "field",
  "money",
  "bid",
  "result",
  "after",
];
export type WatchCard = ItemCard & { step: WatchStep; in_compare: boolean; changed?: boolean };
export type Compare = {
  items: string[];
  excluded: {
    item_id: string;
    reason: string;
    at: string;
    case_no: string | null;
    place: string | null;
  }[];
  max: number;
};
export type SavedSearch = {
  search_id: number;
  name: string;
  filters: Record<string, unknown>;
  delivery: string;
};
export type Noti = {
  noti_id: number;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
  kind?: string | null;
};

export type Bid = {
  bid_id: number;
  item_id: string;
  sale_date: string;
  outcome: string;
  my_bid_krw: number | null;
  winning_bid_krw: number | null;
  second_bid_krw: number | null;
  bidder_count: number | null;
  pay_date: string | null;
  place: string | null;
  court_code: string | null;
  case_no: string | null;
  schedule?: Schedule;
};
export type BidTodo = { item_id: string; sale_date: string; place: string };
export type Bids = { won: Bid[]; history: Bid[]; todo: BidTodo[] };
export type BidIn = {
  item_id: string;
  sale_date: string;
  outcome: string;
  my_bid_krw?: number | null;
  winning_bid_krw?: number | null;
  second_bid_krw?: number | null;
  bidder_count?: number | null;
  pay_date?: string | null;
};

export type LadderRow = {
  section: string;
  rank_no: string;
  name: string;
  date: string | null;
  amount_krw: number | null;
  holder: string;
  judgment: string;
  is_base: boolean;
  mark: "추정" | "내가 고침" | null;
};
export type Ladder = {
  base: { name: string; date: string | null } | null;
  rows: LadderRow[];
  tenants: {
    name: string | null;
    move_in: string | null;
    deposit_krw: number | null;
    verdict: string;
    power: boolean | null;
  }[];
  hold_krw: number;
  line: string;
  state: string;
  spec_check?: { same: boolean; spec: string; spec_date: string; registry_date: string } | null;
  payout: {
    price_krw: number;
    rows: { name: string; claim_krw: number | null; paid_krw: number }[];
    surplus_krw: number;
    unknown: string[];
  } | null;
};
export type RegistryUpload = {
  upload_id: number;
  file_name: string | null;
  status: "processing" | "parsed" | "failed";
  method: string | null;
  error: string | null;
  delete_after: string;
  ladder: Ladder | null;
  created_at?: string;
  choices?: Record<string, string[]>;
  address?: {
    result: "same" | "unit_differs" | "different" | "unknown";
    registry?: string;
    item?: string;
    registry_unit?: string | null;
    item_unit?: string | null;
    ok: boolean;
  };
};

// 등기부 PDF 올리기 (multipart 라 공통 call 을 쓰지 않음)
export async function uploadRegistry(token: string, itemId: string, file: File): Promise<void> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${apiBaseUrl}/me/registries/${encodeURIComponent(itemId)}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  if (!res.ok) {
    const j = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(j?.detail ?? `HTTP ${res.status}`);
  }
}

// 로그인한 사람의 자료. 토큰은 Supabase 세션에서.
// 읽기(GET)는 잠깐 기억하고 같은 요청은 한 번만 보냄(client.ts). 바꾸는 요청은 끝나면 기억을 비움.
// 등기부처럼 읽는 중 상태를 3초마다 확인하는 것은 fresh 로 기억을 건너뜀.
async function call<T>(
  token: string,
  path: string,
  init?: RequestInit & { fresh?: boolean },
): Promise<T> {
  const method = init?.method ?? "GET";
  if (method === "GET" && !init?.fresh) return getMine<T>(token, `/me${path}`);
  try {
    const res = await fetch(`${apiBaseUrl}/me${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
      },
      cache: "no-store",
    });
    if (!res.ok) throw new ApiError(res.status);
    return (await res.json()) as T;
  } finally {
    if (method !== "GET") clearMeCache();
  }
}

export type Workspace = {
  step: WatchStep;
  memo: string;
  checks: Record<string, string>;
  calcs: { bid_krw: number; cash_krw: number | null; saved_at: string }[];
  history: { at: string; what: string; change: string }[];
};

export type CompareFull = Compare & {
  cols: { id: string; d: ItemDetail | null; calc: Calc | null; w: Workspace | null }[];
};

export type MockIn = {
  item_id: string;
  decision: "bid" | "skip";
  bid_krw: number | null;
  max_krw: number | null;
  reason: string | null;
};
export type Mock = MockIn & {
  mock_id: number;
  sale_date: string;
  place: string | null;
  review: string[];
};

export const meApi = {
  mocks: (t: string) => call<Mock[]>(t, "/mocks"),
  saveMock: (t: string, m: MockIn) =>
    call(t, "/mocks", { method: "POST", body: JSON.stringify(m) }),
  removeMock: (t: string, id: number) => call(t, `/mocks/${id}`, { method: "DELETE" }),
  compare: (t: string) => call<Compare>(t, "/compare"),
  /** 비교함 화면 전부(담은 물건마다 상세·계산·작업 공간) 한 번에. */
  compareFull: (t: string, homes: number, first: boolean) =>
    call<CompareFull>(t, `/compare/full?homes=${homes}${first ? "&first=true" : ""}`),
  addCompare: (t: string, id: string) =>
    call(t, `/compare/${encodeURIComponent(id)}`, { method: "PUT" }),
  removeCompare: (t: string, id: string) =>
    call(t, `/compare/${encodeURIComponent(id)}`, { method: "DELETE" }),
  exclude: (t: string, id: string, reason: string) =>
    call(t, `/compare/${encodeURIComponent(id)}/exclude`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  unexclude: (t: string, id: string) =>
    call(t, `/compare/excluded/${encodeURIComponent(id)}`, { method: "DELETE" }),
  workspace: (t: string, id: string) =>
    call<Workspace>(t, `/watch/${encodeURIComponent(id)}/workspace`),
  saveMemo: (t: string, id: string, memo: string) =>
    call(t, `/watch/${encodeURIComponent(id)}/memo`, {
      method: "PUT",
      body: JSON.stringify({ memo }),
    }),
  check: (t: string, id: string, key: string, done: boolean) =>
    call(t, `/watch/${encodeURIComponent(id)}/check`, {
      method: "PUT",
      body: JSON.stringify({ key, done }),
    }),
  addCalc: (t: string, id: string, bid_krw: number, cash_krw: number | null) =>
    call(t, `/watch/${encodeURIComponent(id)}/calcs`, {
      method: "POST",
      body: JSON.stringify({ bid_krw, cash_krw }),
    }),
  removeCalc: (t: string, id: string, bid: number) =>
    call(t, `/watch/${encodeURIComponent(id)}/calcs/${bid}`, { method: "DELETE" }),
  watch: (t: string) => call<WatchCard[]>(t, "/watch"),
  /** 홈 화면 내 자료 한 번에(관심·알림·비교함에서 뺀 물건). */
  home: (t: string) =>
    call<{ watch: WatchCard[]; notifications: Noti[]; excluded: string[] }>(t, "/home"),
  watchIds: (t: string) => call<string[]>(t, "/watch/ids"),
  addWatch: (t: string, id: string) =>
    call(t, `/watch/${encodeURIComponent(id)}`, { method: "PUT" }),
  setStep: (t: string, id: string, step: WatchStep) =>
    call(t, `/watch/${encodeURIComponent(id)}/step`, {
      method: "PUT",
      body: JSON.stringify({ step }),
    }),
  removeWatch: (t: string, id: string) =>
    call(t, `/watch/${encodeURIComponent(id)}`, { method: "DELETE" }),
  searches: (t: string) => call<SavedSearch[]>(t, "/searches"),
  addSearch: (t: string, name: string, filters: Record<string, unknown>) =>
    call<SavedSearch>(t, "/searches", {
      method: "POST",
      body: JSON.stringify({ name, filters, delivery: "daily" }),
    }),
  notifications: (t: string) => call<Noti[]>(t, "/notifications"),
  saveProfile: (t: string, p: { regions: string[]; cash: number | null; purpose: string | null }) =>
    call(t, "/profile", { method: "PUT", body: JSON.stringify(p) }),
  bids: (t: string) => call<Bids>(t, "/bids"),
  registry: (t: string, id: string) =>
    call<RegistryUpload | null>(t, `/registries/${encodeURIComponent(id)}`, { fresh: true }),
  acceptAddress: (t: string, id: string) =>
    call<RegistryUpload | null>(t, `/registries/${encodeURIComponent(id)}/address-ok`, {
      method: "POST",
    }),
  fixRight: (t: string, id: string, b: { section: string; rank_no: string; purpose: string }) =>
    call<RegistryUpload | null>(t, `/registries/${encodeURIComponent(id)}/rights`, {
      method: "PATCH",
      body: JSON.stringify(b),
    }),
  saveBid: (t: string, b: BidIn) => call(t, "/bids", { method: "PUT", body: JSON.stringify(b) }),
  report: (t: string, b: { item_id: string; section: string; note: string }) =>
    call<{ report_id: number }>(t, "/reports", { method: "POST", body: JSON.stringify(b) }),
  addPush: (t: string, sub: { endpoint: string; p256dh: string; auth: string }) =>
    call(t, "/push", { method: "POST", body: JSON.stringify(sub) }),
};
