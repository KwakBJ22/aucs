import { expect, test } from "@playwright/test";
import { login, open, pickItems, watchErrors } from "./helpers";

// 휴대폰: 찾기(말로 찾기) → 상세 → 입찰가 계산 → 보고서 → 공매 상세 → (로그인) 관심 담기·빼기 → 모의입찰 남기기·지우기 → 내 경매
test.describe.configure({ mode: "serial" });

test("말로 찾기 → 조건 칩", async ({ page }) => {
  const errs = watchErrors(page);
  await open(page, "/find");
  await page.locator('input[type="search"]').fill("수지 30평대 7억 이하");
  await expect(page.getByText("알아들은 조건")).toBeVisible();
  await expect(page.getByText(/최저가 7억 이하/)).toBeVisible();
  await expect(page.getByText(/30평대/).first()).toBeVisible();
  expect(errs).toEqual([]);
});

test("경매 상세 → 입찰가 계산 → 보고서", async ({ page }) => {
  const errs = watchErrors(page);
  const { court } = await pickItems(page);
  const id = encodeURIComponent(court);
  await open(page, `/item/${id}`);
  await expect(page.locator("h1, h2").first()).toBeVisible();
  await open(page, `/item/${id}/calc`);
  await page.getByRole("button", { name: "없어요" }).click(); // 집 몇 채 — 골라야 계산이 나옴(새 브라우저는 저장된 답이 없음)
  const slider = page.getByRole("slider", { name: "입찰가 넣어 보기" });
  await expect(slider).toBeVisible();
  await slider.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByText(/\d억|\d만/).first()).toBeVisible(); // 금액(숨은 PC 머리의 「3초 만에」는 빼려고 숫자 붙은 것만)
  await open(page, `/item/${id}/report`);
  await expect(page.getByText(/감정가|최저가/).first()).toBeVisible();
  expect(errs).toEqual([]);
});

test("공매 상세", async ({ page }) => {
  const errs = watchErrors(page);
  await open(page, "/find?source=onbid"); // 공매만 보기(첫 화면에 공매가 없을 때도 시험되게)
  const link = page.locator('a[href^="/item/OB-"]').first();
  const onbid = (await link.waitFor({ timeout: 20000 }).then(
    () => true,
    () => false,
  ))
    ? decodeURIComponent(
        ((await link.getAttribute("href")) ?? "").replace("/item/", "").split("/")[0] ?? "",
      )
    : null;
  test.skip(!onbid, "공매 목록이 비어 있음");
  await open(page, `/item/${encodeURIComponent(onbid as string)}`);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible(); // 주소 제목(숨은 PC 메뉴 「공매」는 빼고)
  expect(errs).toEqual([]);
});

test("로그인 → 관심 담기·빼기 → 모의입찰 남기기·지우기 → 내 경매", async ({ page }) => {
  const errs = watchErrors(page);
  const { court } = await pickItems(page);
  test.skip(
    !(await login(page)),
    ".env 에 SUPABASE_URL·SUPABASE_SECRET_KEY 가 없어 로그인 시험은 건너뜀",
  );
  const id = encodeURIComponent(court);
  await open(page, `/item/${id}`);
  await page.waitForLoadState("networkidle"); // 관심 여부를 받아 온 뒤에 하트를 봄(먼저 누르면 상태가 엇갈림)
  const off = page.getByRole("button", { name: "관심 빼기" }).first();
  if (await off.isVisible().catch(() => false)) {
    await off.click(); // 지난 시험 찌꺼기
    await page.waitForLoadState("networkidle");
  }
  await page.getByRole("button", { name: "관심 담기" }).first().click();
  const later = page.getByRole("button", { name: "나중에" }); // 처음이면 홈 화면 추가 안내
  if (await later.isVisible().catch(() => false)) await later.click();
  await expect(page.getByRole("button", { name: "관심 빼기" }).first()).toBeVisible();
  await open(page, "/watch");
  await expect(page.locator(`a[href^="/item/${id}"]`).first()).toBeVisible();
  // 모의입찰
  await open(page, `/item/${id}/calc`);
  const mockOpen = page.getByText("모의입찰 남기기");
  if (await mockOpen.isVisible().catch(() => false)) {
    await mockOpen.click();
    await page.getByRole("button", { name: "남기기" }).click();
    await expect(page.getByText(/남겼어요/)).toBeVisible();
  }
  await open(page, "/me");
  await expect(page.getByRole("heading", { name: "내 경매", level: 1 })).toBeVisible(); // 숨은 PC 메뉴 「내 경매」는 빼고
  const rm = page.getByRole("button", { name: "지우기" });
  while ((await rm.count()) > 0) {
    await rm.first().click();
    await page.waitForTimeout(500);
  }
  // 관심 빼기(시험 흔적 지움)
  await open(page, `/item/${id}`);
  await page.getByRole("button", { name: "관심 빼기" }).first().click();
  await expect(page.getByRole("button", { name: "관심 담기" }).first()).toBeVisible();
  expect(errs).toEqual([]);
});
