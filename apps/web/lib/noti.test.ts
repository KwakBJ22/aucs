import { describe, expect, it } from "vitest";
import { isStale } from "./noti";

describe("isStale", () => {
  const now = new Date(2026, 10, 1, 18);
  it("입찰일 아침은 그날만", () => {
    expect(isStale({ kind: "bid_morning", created_at: "2026-10-19T22:42:00+09:00" }, now)).toBe(
      true,
    );
    expect(
      isStale({ kind: "bid_morning", created_at: new Date(2026, 10, 1, 7).toISOString() }, now),
    ).toBe(false);
  });
  it("일반 변경 알림은 그대로", () => {
    expect(isStale({ kind: "price_drop", created_at: "2026-09-01T00:00:00Z" }, now)).toBe(false);
  });
});
