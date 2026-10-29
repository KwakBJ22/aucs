import { expect, type Page } from "@playwright/test";

export const API = process.env.E2E_API ?? "http://localhost:8100";

// 화면마다: 멈춤 화면(error.tsx)이 안 뜨고, 잡지 못한 오류가 없어야 함
export function watchErrors(page: Page): string[] {
  const errs: string[] = [];
  page.on("pageerror", (e) => errs.push(e.message));
  return errs;
}

export async function open(page: Page, path: string) {
  const res = await page.goto(path);
  expect(res?.status(), `${path} 응답`).toBeLessThan(400);
  await expect(page.getByText("이 화면에서 문제가 생겼어요")).toHaveCount(0);
}

// 찾기 목록에서 경매·공매 물건 하나씩
export async function pickItems(page: Page): Promise<{ court: string; onbid: string | null }> {
  await open(page, "/find");
  const links = page.locator('a[href^="/item/"]');
  await expect(links.first()).toBeVisible();
  const hrefs = await links.evaluateAll((xs) => xs.map((x) => x.getAttribute("href") ?? ""));
  const ids = hrefs.map((h) => decodeURIComponent(h.replace("/item/", "").split("/")[0] ?? ""));
  const court = ids.find((x) => x && !x.startsWith("OB-"));
  expect(court, "찾기 목록에 경매 물건").toBeTruthy();
  return { court: court as string, onbid: ids.find((x) => x.startsWith("OB-")) ?? null };
}

// 시험용 회원으로 로그인(.env 의 SUPABASE_SECRET_KEY 로 메일 링크를 바로 만들어 엶). 키가 없으면 false.
export async function login(page: Page): Promise<boolean> {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SECRET_KEY;
  if (!url || !key) return false;
  const email = process.env.E2E_EMAIL ?? "e2e-test@aucs.co.kr";
  const h = { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json" };
  await fetch(`${url}/auth/v1/admin/users`, {
    method: "POST",
    headers: h,
    body: JSON.stringify({ email, email_confirm: true }),
  }); // 이미 있으면 422 — 상관없음
  const base = process.env.E2E_BASE ?? "http://localhost:3000";
  const r = await fetch(`${url}/auth/v1/admin/generate_link`, {
    method: "POST",
    headers: h,
    body: JSON.stringify({ type: "magiclink", email, redirect_to: `${base}/home` }),
  });
  const d = (await r.json()) as { action_link?: string; properties?: { action_link?: string } };
  const link = d.action_link ?? d.properties?.action_link;
  expect(link, "로그인 링크").toBeTruthy();
  await page.goto(link as string);
  await page.waitForURL(/\/home|\/start/, { timeout: 30_000 });
  return true;
}
