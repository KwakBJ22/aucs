import { describe, expect, it } from "vitest";
import { dday, won } from "./format";

describe("won", () => {
  it("억·만", () => {
    expect(won(710_500_000)).toBe("7억 1,050만");
    expect(won(92_670_000)).toBe("9,267만");
    expect(won(300_000_000)).toBe("3억");
    expect(won(null)).toBe("-");
  });
  it("D-day", () => expect(dday(0)).toBe("D-day"));
});
