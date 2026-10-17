import { describe, expect, it } from "vitest";
import { toHealthState } from "./health";

describe("toHealthState", () => {
  it("ok 응답은 정상", () => expect(toHealthState({ ok: true })).toBe("ok"));
  it("ok:false 와 응답 없음은 안 됨", () => {
    expect(toHealthState({ ok: false })).toBe("fail");
    expect(toHealthState(null)).toBe("fail");
  });
});
