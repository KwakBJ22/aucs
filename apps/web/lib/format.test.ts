import { describe, expect, it } from "vitest";
import { dday, won, wonShort } from "./format";

describe("won", () => {
  it("억·만", () => {
    expect(won(710_500_000)).toBe("7억\u00a01,050만");
    expect(won(92_670_000)).toBe("9,267만");
    expect(won(300_000_000)).toBe("3억");
    expect(won(null)).toBe("-");
    expect(won(4_762_475_800_000)).toBe("4조\u00a07,624억");
    expect(won(1_000_000_000_000)).toBe("1조");
  });
  it("짧은 금액", () => {
    expect(wonShort(1_040_000_000)).toBe("10.4억");
    expect(wonShort(300_000_000)).toBe("3억");
    expect(wonShort(98_000_000)).toBe("9,800만");
  });
  it("D-day", () => expect(dday(0)).toBe("D-day"));
  it("지난 날", () => expect(dday(-8)).toBe("8일 지남"));
});
