import { describe, expect, it } from "vitest";
import { formatBytes } from "./admin";

describe("formatBytes", () => {
  it("MB로 반올림", () => expect(formatBytes(431_000_000)).toBe("411MB"));
});
