import { apiBaseUrl } from "./client";

// 관리자 주소 호출(11/2): 옥스 로그인 토큰으로. 권한이 없으면 "denied", 2단계 인증 전이면 "mfa".
export type Role = "owner" | "operator" | "viewer";
export type JobRun = {
  job_id: string;
  name_ko: string;
  status: string;
  item_count: number | null;
  started_at: string;
  finished_at: string | null;
  message?: string | null;
};
export type Today = {
  red: { kind: string; text: string; go: string }[];
  yesterday: {
    new_items: number;
    new_users: number;
    devices: number;
    views: number;
    errors: number;
  };
  open: { reports: number; inquiries: number };
  // 유료 전환 가늠(11/12): 관심 담은 진행 물건 중 서류가 찬 수
  fill?: {
    members: number;
    uploaders: number;
    week: number;
    watched: number;
    registry: number;
    appraisal: number;
  };
  steps: JobRun[];
  db: { used: number; limit: number };
  backup: { at: string; status: string; message: string | null } | null;
  restore: { at: string; status: string } | null;
};
export type JobRow = JobRun & { days: { day: string; s: "ok" | "bad" | "run" }[] };
export type JobReq = {
  req_id: number;
  job_key: string;
  requested_at: string;
  status: string;
  message: string | null;
};
export type Jobs = {
  jobs: JobRow[];
  requests: JobReq[];
  first_day: string;
  requestable: Record<string, string>;
};
export type ErrorRow = {
  side: string;
  message: string;
  n: number;
  devices: number;
  last_at: string;
  path: string | null;
  stack: string | null;
};
export type Review = {
  total: { reports: number; fields: number; signals: number };
  reports: {
    report_id: number;
    item_id: string;
    section: string;
    note: string;
    created_at: string;
    address: string | null;
    sale_date: string | null;
  }[];
  fields: {
    field_id: number;
    case_id: string;
    doc_kind: string;
    field: string;
    value: unknown;
    raw_text: string | null;
    sale_date: string | null;
  }[];
  signals: {
    signal_id: number;
    item_id: string;
    rule_id: string;
    level: string;
    title: string;
    sale_date: string;
    address: string | null;
  }[];
};
export type UserRow = {
  user_id: string;
  email: string;
  nickname: string | null;
  created_at: string;
  last_sign_in_at: string | null;
  plan: string | null;
  watch_n: number;
  limited: boolean;
  admin_role: Role | null;
};
export type Inquiry = {
  inquiry_id: number;
  user_id?: string | null;
  email?: string;
  body: string;
  answer: string | null;
  created_at: string;
  answered_at: string | null;
};
export type UserDetail = UserRow & {
  interest_regions: string[] | null;
  purpose: string | null;
  search_n: number;
  noti_n: number;
  bid_n: number;
  registry_n: number;
  mock_n: number;
  limit_reason: string | null;
  grants: { plan: string; until_date: string; reason: string; created_at: string }[];
  inquiries: Inquiry[];
};
export type RefundReq = {
  request_id: number;
  payment_id: number;
  estimate_krw: number;
  reason: string | null;
  created_at: string;
  plan: string;
  period: string;
  amount_krw: number;
  paid_at: string;
  order_id: string | null;
  email: string;
};
export type Notice = {
  notice_id: number;
  title: string;
  body: string;
  start_at: string;
  end_at: string | null;
  pinned: boolean;
};
export type Flag = { flag_key: string; enabled: boolean; note: string | null };
export type RuleRow = {
  rule_key: string;
  valid_from: string;
  valid_to: string | null;
  value: unknown;
  basis: string;
  reviewed_at: string | null;
};
export type DongAlias = {
  sido: string;
  city: string;
  old_name: string;
  new_name: string;
  changed_on: string | null;
};
export type AdminRow = { user_id: string; email: string; role: Role; added_at: string };
export type AuditRow = {
  audit_id: number;
  at: string;
  action: string;
  target: string;
  actor: string;
  note: string | null;
};

export class AdminError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

async function call<T>(token: string, path: string, method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(`${apiBaseUrl}/admin${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = ((await res.json()) as { detail?: string }).detail ?? detail;
    } catch {
      /* 내용 없음 */
    }
    if (res.status === 403 && detail === "mfa") throw new AdminError(403, "mfa");
    if (res.status === 401 || (res.status === 403 && detail === "관리자 권한이 없습니다"))
      throw new AdminError(res.status, "denied");
    throw new AdminError(res.status, detail);
  }
  return (await res.json()) as T;
}

const enc = encodeURIComponent;
export type Metrics = {
  devices: number;
  started: number;
  viewed: number;
  watched: number;
  calc: number;
  first_item_sec: number | null;
  cohort: number;
  returned: number;
};
export type Stats = {
  weeks: {
    wk: string;
    devices: number;
    views: number;
    watched: number;
    calc: number;
    new_users: number;
  }[];
  top: {
    item_id: string;
    views: number;
    devices: number;
    address: string | null;
    sale_date: string | null;
  }[];
};
export type Screens = {
  jobs: { jobs: Jobs; errors: ErrorRow[] };
  review: {
    review: Review;
    hidden: { item_id: string; address: string | null; sale_date: string | null }[];
  };
  members: { users: UserRow[]; inquiries: Inquiry[]; refunds: RefundReq[] };
  stats: { status: { metrics?: Metrics }; stats: Stats };
  settings: {
    rules: RuleRow[];
    flags: Flag[];
    dongs: DongAlias[];
    admins: AdminRow[];
    audit: AuditRow[];
  };
};
export type PointReview = {
  contrib_id: number;
  item_id: string;
  case_id: string;
  created_at: string;
};

// 포인트 벌기 확인용 원본(잠긴 보관함이라 서버가 대신 받아 줌, 11/12) — 새 창에서 열 수 있게 파일 주소로
export async function pointReviewPdf(token: string, id: number): Promise<string> {
  const res = await fetch(`${apiBaseUrl}/admin/points/review/${id}/pdf`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) throw new AdminError(res.status, `HTTP ${res.status}`);
  return URL.createObjectURL(await res.blob());
}

export const adminApi = {
  pointReviews: (t: string) => call<PointReview[]>(t, "/points/review"),
  decidePoint: (t: string, id: number, ok: boolean) =>
    call(t, `/points/review/${id}`, "PUT", { ok }),
  // 메뉴 한 화면 자료 한 번에(11/3 — 예전 메뉴마다 2~5번)
  screen: <K extends keyof Screens>(t: string, menu: K, days?: number) =>
    call<Screens[K]>(t, `/screen/${menu}${days ? `?days=${days}` : ""}`),
  stats: (t: string, days: number) => call<Stats>(t, `/stats?days=${days}`),
  status: (t: string) => call<{ metrics?: Metrics }>(t, "/status"),
  me: (t: string) => call<{ role: Role; mfa: boolean }>(t, "/me"),
  today: (t: string) => call<Today>(t, "/today"),
  jobs: (t: string) => call<Jobs>(t, "/jobs"),
  markStale: (t: string) => call<{ n: number }>(t, "/jobs/mark-stale", "POST"),
  requestJob: (t: string, job_key: string) =>
    call<{ req_id: number; dup: boolean }>(t, "/job-requests", "POST", { job_key }),
  errors: (t: string) => call<ErrorRow[]>(t, "/errors"),
  errorFixed: (t: string, side: string, message: string) =>
    call(t, "/errors/fixed", "POST", { side, message }),
  review: (t: string) => call<Review>(t, "/review"),
  closeReport: (t: string, id: number, status: "fixed" | "rejected") =>
    call(t, `/reports/${id}`, "PUT", { status }),
  checkField: (t: string, id: number, value?: unknown) =>
    call(t, `/fields/${id}`, "PUT", { value: value ?? null }),
  decideSignal: (t: string, item_id: string, rule_id: string, status: "확정" | "없음") =>
    call(t, "/signals", "PUT", { item_id, rule_id, status }),
  hide: (t: string, id: string, hidden: boolean, reason?: string) =>
    call(t, `/items/${enc(id)}/hide`, "PUT", { hidden, reason: reason ?? null }),
  hidden: (t: string) =>
    call<{ item_id: string; address: string | null; sale_date: string | null }[]>(
      t,
      "/items/hidden",
    ),
  refunds: (t: string) => call<RefundReq[]>(t, "/refunds"),
  decideRefund: (t: string, id: number, ok: boolean, answer: string, amount_krw?: number) =>
    call(t, `/refunds/${id}`, "PUT", { ok, answer, amount_krw: amount_krw ?? null }),
  users: (t: string, q: string) => call<UserRow[]>(t, `/users?q=${enc(q)}`),
  user: (t: string, id: string) => call<UserDetail>(t, `/users/${id}`),
  revealEmail: (t: string, id: string) => call<{ email: string }>(t, `/users/${id}/email`, "POST"),
  grant: (t: string, id: string, plan: string, days: number, reason: string) =>
    call(t, `/users/${id}/grants`, "POST", { plan, days, reason }),
  limit: (t: string, id: string, reason: string | null) =>
    call(t, `/users/${id}/limit`, "PUT", { reason }),
  inquiries: (t: string, all = false) => call<Inquiry[]>(t, `/inquiries${all ? "?all=true" : ""}`),
  answer: (t: string, id: number, answer: string) => call(t, `/inquiries/${id}`, "PUT", { answer }),
  notices: (t: string) => call<Notice[]>(t, "/notices"),
  saveNotice: (t: string, n: Partial<Notice> & { title: string }, id?: number) =>
    call<Notice>(t, id ? `/notices/${id}` : "/notices", id ? "PUT" : "POST", n),
  endNotice: (t: string, id: number) => call(t, `/notices/${id}/end`, "POST"),
  flags: (t: string) => call<Flag[]>(t, "/flags"),
  setFlag: (t: string, key: string, enabled: boolean) =>
    call<Flag>(t, `/flags/${enc(key)}`, "PUT", { enabled }),
  rules: (t: string) => call<RuleRow[]>(t, "/rule-tables"),
  newRule: (t: string, key: string, valid_from: string, value: unknown, basis: string) =>
    call(t, `/rule-tables/${enc(key)}`, "POST", { valid_from, value, basis }),
  ruleReviewed: (t: string, key: string, from: string) =>
    call(t, `/rule-tables/${enc(key)}/${from}/reviewed`, "POST"),
  dongAlias: (t: string) => call<DongAlias[]>(t, "/dong-alias"),
  addDong: (t: string, d: DongAlias) => call(t, "/dong-alias", "POST", d),
  admins: (t: string) => call<AdminRow[]>(t, "/admins"),
  addAdmin: (t: string, email: string, role: Role) => call(t, "/admins", "POST", { email, role }),
  removeAdmin: (t: string, id: string) => call(t, `/admins/${id}`, "DELETE"),
  audit: (t: string) => call<AuditRow[]>(t, "/audit"),
};

export function formatBytes(n: number): string {
  return `${Math.round(n / 1024 / 1024)}MB`;
}

export const can = (role: Role, need: Role) =>
  ({ viewer: 1, operator: 2, owner: 3 })[role] >= { viewer: 1, operator: 2, owner: 3 }[need];
