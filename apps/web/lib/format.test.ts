import { describe, expect, it } from "vitest";
import { dday, parseTime, won, wonShort } from "./format";

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

// 11/14: 날짜만 있는 값의 끝 「-01」을 시간대로 읽어 관리자 「작업·수집」 화면이 깨졌음
describe("parseTime", () => {
  it("날짜만 있어도 읽는다", () => {
    expect(parseTime("2026-11-01").toISOString()).toBe("2026-11-01T00:00:00.000Z");
  });
  it("DB 시각(+00)도 읽는다", () => {
    expect(parseTime("2026-11-14 02:28:19.543802+00").toISOString()).toBe(
      "2026-11-14T02:28:19.543Z",
    );
  });
});
