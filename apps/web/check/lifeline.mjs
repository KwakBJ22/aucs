// 배포 전 목숨줄 검사(11/3): 돈·로그인 길 6개를 실제 화면으로 한 바퀴. 서버 답은 가짜(밖으로 안 나감).
// 하나라도 실패하면 exit 1 + 실패한 길 이름. 실패한 길만 사진(check/failed/).
// 실행: node apps/web/check/lifeline.mjs [화면 주소]   (기본 http://localhost:3000)
//   LIFELINE_URL     화면 주소(인자 대신)
//   LIFELINE_BYPASS  Vercel 미리보기 보호를 넘는 값(배포 배치가 넣음)
//   LIFELINE_CHROME  "0"이면 깔린 크롬 대신 Playwright 크로미움
//   LIFELINE_CHROME_PATH  브라우저 실행 파일을 직접 지정
//   LIFELINE_REF     Supabase 프로젝트 ref(기본 옥스)
import { mkdirSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try {
  ({ chromium } = await import("@playwright/test"));
} catch {
  ({ chromium } = await import("playwright"));
}

const here = path.dirname(fileURLToPath(import.meta.url));
const BASE = (process.argv[2] ?? process.env.LIFELINE_URL ?? "http://localhost:3000").replace(/\/$/, "");
const REF = process.env.LIFELINE_REF ?? "ewwdcrtlsdjyvqfqzznv";
const FAILED = path.join(here, "failed");
const ITEM = JSON.parse(readFileSync(path.join(here, "fixtures", "item.json"), "utf8"));
const EMAIL = "lifeline@aucs.test";
const STEP = 8_000;

// ── 가짜 로그인(aal2, 1시간 유효) ──
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
const now = Math.floor(Date.now() / 1000);
const USER = {
  id: "00000000-0000-4000-8000-000000000001",
  aud: "authenticated",
  role: "authenticated",
  email: EMAIL,
  email_confirmed_at: "2026-11-01T00:00:00Z",
  app_metadata: { provider: "email" },
  user_metadata: {},
  factors: [],
  created_at: "2026-11-01T00:00:00Z",
};
const JWT = `${b64({ alg: "HS256", typ: "JWT" })}.${b64({
  sub: USER.id,
  email: EMAIL,
  aud: "authenticated",
  role: "authenticated",
  aal: "aal2",
  amr: [{ method: "otp", timestamp: now }, { method: "totp", timestamp: now }],
  session_id: "lifeline",
  iat: now,
  exp: now + 3600,
})}.lifeline`;
const SESSION = {
  access_token: JWT,
  refresh_token: "lifeline-refresh",
  token_type: "bearer",
  expires_in: 3600,
  expires_at: now + 3600,
  user: USER,
};

// ── 가짜 서버 답 ──
const BILLING = {
  current: [
    { plan: "personal", until: "2027-11-01", auto_renew: false, period: "year", amount_krw: 290000, item_id: null },
  ],
  payments: [
    {
      payment_id: 1,
      plan: "personal",
      period: "year",
      amount_krw: 290000,
      item_id: null,
      status: "paid",
      refunded_krw: 0,
      auto_renew: false,
      method_note: "카드",
      order_id: "LIFE-1",
      receipt_url: null,
      paid_at: "2026-11-01T09:00:00+09:00",
      valid_from: "2026-11-01",
      valid_to: "2027-11-01",
      refund_status: null,
      refund: { amount_krw: 290000, rule: "7일 안 · 상세를 안 열어 봄 → 전액" },
    },
  ],
  grants: [],
};
const TODAY = {
  red: [],
  yesterday: { new_items: 1, new_users: 1, devices: 1, views: 1, errors: 0 },
  open: { reports: 0, inquiries: 0 },
  steps: [],
  db: { used: 1, limit: 8 * 1024 ** 3 },
  backup: null,
  restore: null,
};

function apiAnswer(method, p, hit) {
  if (/^\/items\/[^/]+$/.test(p)) return ITEM;
  if (p === "/me/billing") return BILLING;
  if (method === "POST" && /^\/me\/billing\/\d+\/refund$/.test(p)) {
    hit.refund = true;
    return { estimate_krw: 290000, rule: "전액" };
  }
  if (p === "/admin/me") return { role: "owner", mfa: true };
  if (p === "/admin/today") return TODAY;
  return undefined;
}

function supaAnswer(method, p, hit) {
  if (p === "/auth/v1/otp") {
    hit.otp = true;
    return {};
  }
  if (p === "/auth/v1/user") return USER;
  if (p === "/auth/v1/token") return SESSION;
  if (p === "/auth/v1/logout") return {};
  if (p.startsWith("/auth/v1/factors")) return { all: [], totp: [], phone: [] };
  if (p.startsWith("/rest/v1/")) return [];
  return {};
}

async function wire(ctx, hit) {
  const origin = new URL(BASE).origin;
  await ctx.route("**/*", async (route) => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.origin === origin) return route.continue();
    if (!/^https?:$/.test(u.protocol)) return route.continue();
    const cors = {
      "access-control-allow-origin": origin,
      "access-control-allow-headers": "*",
      "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
      "access-control-allow-credentials": "true",
    };
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const supa = u.hostname.endsWith("supabase.co");
    const body = supa ? supaAnswer(req.method(), u.pathname, hit) : apiAnswer(req.method(), u.pathname, hit);
    if (body === undefined)
      return route.fulfill({ status: 404, headers: cors, contentType: "application/json", body: '{"detail":"lifeline"}' });
    return route.fulfill({ status: 200, headers: cors, contentType: "application/json", body: JSON.stringify(body) });
  });
}

// ── 길 6개 ──
const phone = { viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true };
const pc = { viewport: { width: 1440, height: 900 } };
const seen = (page, text) => page.getByText(text, { exact: false }).first().waitFor({ state: "visible", timeout: STEP });

const PATHS = [
  {
    name: "로그인 링크 받기",
    dev: phone,
    login: false,
    run: async (page, hit) => {
      await page.goto(`${BASE}/login`);
      await page.locator('input[type="email"]').fill(EMAIL);
      await page.getByRole("button", { name: "로그인 링크 받기" }).click();
      await seen(page, "메일함에서 링크를 누르면 로그인돼요");
      if (!hit.otp) throw new Error("로그인 링크 요청이 나가지 않았어요");
    },
  },
  {
    name: "로그인 유지",
    dev: phone,
    login: true,
    run: async (page) => {
      await page.goto(`${BASE}/login`);
      await seen(page, `${EMAIL}로 로그인했어요`);
      await page.reload();
      await seen(page, `${EMAIL}로 로그인했어요`);
    },
  },
  {
    name: "이용권 화면",
    dev: phone,
    login: false,
    run: async (page) => {
      await page.goto(`${BASE}/plans`);
      await seen(page, "29,000원");
      await page.getByRole("tab", { name: /1년/ }).click();
      await seen(page, "249,000원"); // 11/12 1년 290,000 → 249,000
    },
  },
  {
    name: "결제 내역·환불 요청",
    dev: phone,
    login: true,
    run: async (page, hit) => {
      await page.goto(`${BASE}/more/billing`);
      await seen(page, "결제 내역");
      await page.getByRole("button", { name: /개인 · 1년/ }).click();
      await seen(page, "지금 환불하면 290,000원");
      await page.getByRole("button", { name: "환불 요청" }).click();
      await seen(page, "290,000원을 돌려받도록 요청할까요?");
      await page.getByRole("button", { name: "환불 요청" }).click();
      await seen(page, "환불을 요청했어요");
      if (!hit.refund) throw new Error("환불 요청이 서버로 나가지 않았어요");
    },
  },
  {
    name: "물건 상세 열기",
    dev: phone,
    login: false,
    run: async (page) => {
      await page.goto(`${BASE}/item/${encodeURIComponent(ITEM.item_id)}`);
      await seen(page, ITEM.verdict);
    },
  },
  {
    name: "관리자 들어가기",
    dev: pc,
    login: true,
    run: async (page) => {
      await page.goto(`${BASE}/admin`);
      await seen(page, "모두 정상이에요");
    },
  },
];

// ── 실행 ──
const started = Date.now();
rmSync(FAILED, { recursive: true, force: true });
const useChrome = process.env.LIFELINE_CHROME !== "0";
let browser;
try {
  browser = await chromium.launch(
    process.env.LIFELINE_CHROME_PATH
      ? { executablePath: process.env.LIFELINE_CHROME_PATH }
      : useChrome
        ? { channel: "chrome" }
        : {},
  );
} catch {
  browser = await chromium.launch();
}
const headers = process.env.LIFELINE_BYPASS
  ? { "x-vercel-protection-bypass": process.env.LIFELINE_BYPASS, "x-vercel-set-bypass-cookie": "true" }
  : undefined;

const fails = [];
for (const p of PATHS) {
  const ctx = await browser.newContext({ ...p.dev, locale: "ko-KR", extraHTTPHeaders: headers });
  const hit = {};
  await wire(ctx, hit);
  if (p.login)
    await ctx.addInitScript(
      ([k, v]) => {
        try {
          localStorage.setItem(k, v);
        } catch {
          /* 저장 불가 */
        }
      },
      [`sb-${REF}-auth-token`, JSON.stringify(SESSION)],
    );
  const page = await ctx.newPage();
  page.setDefaultTimeout(STEP);
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  const t0 = Date.now();
  let why = "";
  try {
    await p.run(page, hit);
    await page.waitForTimeout(300);
    if (await page.getByText("이 화면에서 문제가 생겼어요").count()) why = "멈춤 화면이 떴어요";
    else if (errs.length) why = `화면 오류 ${errs.length}개: ${errs[0]}`;
  } catch (e) {
    why = String(e?.message ?? e).split("\n")[0];
    if (errs.length) why += ` (화면 오류: ${errs[0]})`;
  }
  const sec = ((Date.now() - t0) / 1000).toFixed(1);
  if (why) {
    fails.push(p.name);
    mkdirSync(FAILED, { recursive: true });
    await page.screenshot({ path: path.join(FAILED, `${p.name}.png`) }).catch(() => {});
    console.log(`  ✗ ${p.name} (${sec}초) — ${why}`);
  } else console.log(`  ✓ ${p.name} (${sec}초)`);
  await ctx.close();
}
await browser.close();

const total = ((Date.now() - started) / 1000).toFixed(1);
if (fails.length) {
  console.log(`\n목숨줄 검사 빨강 — 실패 ${fails.length}개: ${fails.join(", ")} (${total}초)`);
  console.log(`사진: ${FAILED}`);
  process.exit(1);
}
console.log(`\n목숨줄 검사 초록 — ${PATHS.length}개 모두 통과 (${total}초)`);
