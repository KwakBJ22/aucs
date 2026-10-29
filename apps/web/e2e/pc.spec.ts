import { expect, test } from "@playwright/test";
import { open, watchErrors } from "./helpers";

// PC: 전체 물건 표(옆으로 밀리지 않음·줄 고르면 오른쪽 칸) → 시장 → 공매만
test("전체 물건 표 → 줄 고르기", async ({ page }) => {
  const errs = watchErrors(page);
  await open(page, "/pro/items");
  const rows = page.locator(".pro-table tbody tr");
  await expect(rows.nth(1)).toBeVisible();
  const [w, box] = await page
    .locator(".pro-table")
    .evaluate((t) => [t.clientWidth, t.parentElement?.clientWidth ?? 0]);
  expect(w, "표가 칸보다 넓지 않음").toBeLessThanOrEqual((box as number) + 1);
  await rows.nth(1).click();
  await expect(page.getByText("× 닫고 표 넓게")).toBeVisible();
  await open(page, "/pro/items?source=onbid");
  await expect(rows.first()).toBeVisible();
  expect(errs).toEqual([]);
});

test("시장 화면", async ({ page }) => {
  const errs = watchErrors(page);
  await open(page, "/pro/market");
  await expect(page.locator("main")).toBeVisible();
  expect(errs).toEqual([]);
});
