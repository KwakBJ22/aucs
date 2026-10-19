import { apiBaseUrl } from "./client";
import type { ItemCard, Schedule } from "./items";

export type WatchStep = "review" | "field" | "money" | "bid" | "result";
export type WatchCard = ItemCard & { step: WatchStep };
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
async function call<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBaseUrl}/me${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const meApi = {
  watch: (t: string) => call<WatchCard[]>(t, "/watch"),
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
    call<RegistryUpload | null>(t, `/registries/${encodeURIComponent(id)}`),
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
  addPush: (t: string, sub: { endpoint: string; p256dh: string; auth: string }) =>
    call(t, "/push", { method: "POST", body: JSON.stringify(sub) }),
};
