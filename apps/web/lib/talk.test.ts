import { describe, expect, it } from "vitest";
import { complexName, dropPart, parseTalk } from "./talk";

const R = ["용인시 수지구", "강남구", "성남시 분당구", "화성시 동탄구"];

describe("parseTalk", () => {
  it("수지 30평대 7억 이하", () => {
    const t = parseTalk("수지 30평대 7억 이하", R)!;
    expect(t.sigungu).toEqual(["용인시 수지구"]);
    expect(t.filter.price_max).toBe(700_000_000);
    expect(t.filter.area_min).toBe(75);
    expect(t.filter.area_max).toBe(100);
    expect(t.rest).toBe("");
  });
  it("종류·유찰·기간·공매, 남은 말은 검색어", () => {
    const t = parseTalk("강남 아파트 유찰 2회 이상 이번 주 공매 래미안", R)!;
    expect(t.filter.usage).toEqual(["apt"]);
    expect(t.filter.failed_min).toBe(2);
    expect(t.filter.days_max).toBe(7);
    expect(t.source).toBe("onbid");
    expect(t.rest).toBe("래미안");
  });
  it("7억 5천까지 · 전용 84", () => {
    const t = parseTalk("분당 7억 5천까지 전용 84", R)!;
    expect(t.filter.price_max).toBe(750_000_000);
    expect(t.filter.area_min).toBe(80);
    expect(t.sigungu).toEqual(["성남시 분당구"]);
  });
  it("조건이 없으면 null(사건번호·단지 검색 그대로)", () => {
    expect(parseTalk("2025타경55580", R)).toBeNull();
    expect(parseTalk("래미안", R)).toBeNull();
  });
  it("칩 지우기", () => {
    const t = parseTalk("수지 7억 이하", R)!;
    const u = dropPart(t, "price_max")!;
    expect(u.filter.price_max).toBeUndefined();
    expect(dropPart(u, "region:용인시 수지구")).toBeNull();
  });
});

describe("complexName", () => {
  it("동·층·호를 뺀 단지 이름", () => {
    expect(
      complexName({ building: "버들치마을성복힐스테이트3차 304동 2층203호", place: "수지구" }),
    ).toBe("버들치마을성복힐스테이트3차");
    expect(complexName({ building: null, place: "수지구" })).toBe("수지구");
  });
});
