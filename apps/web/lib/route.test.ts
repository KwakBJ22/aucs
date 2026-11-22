import { describe, expect, it } from "vitest";
import { androidIntent, naverRoute, nearestOrder, type Stop } from "./route";

const A: Stop = { id: "a", name: "방이동 아파트", lat: 37.514, lon: 127.115 };
const B: Stop = { id: "b", name: "잠실 빌라", lat: 37.511, lon: 127.098 }; // A 에서 약 1.5km
const C: Stop = { id: "c", name: "수원 상가", lat: 37.263, lon: 127.028 }; // 멀리

describe("nearestOrder", () => {
  it("첫 곳에서 가까운 순서", () => {
    expect(nearestOrder([A, C, B]).map((x) => x.id)).toEqual(["a", "b", "c"]);
  });
  it("휴대폰 위치가 있으면 거기서 가장 가까운 곳부터", () => {
    expect(nearestOrder([A, B, C], [37.27, 127.03]).map((x) => x.id)).toEqual(["c", "b", "a"]);
  });
  it("빈 목록", () => {
    expect(nearestOrder([])).toEqual([]);
  });
});

describe("naverRoute", () => {
  it("마지막 곳이 도착지 · 앞은 경유지 · appname", () => {
    const u = new URL(naverRoute([A, B, C], "https://aucs.co.kr").replace("nmap://", "https://x/"));
    expect(u.pathname).toBe("/route/car");
    expect(u.searchParams.get("dlat")).toBe("37.263");
    expect(u.searchParams.get("dname")).toBe("수원 상가");
    expect(u.searchParams.get("v1name")).toBe("방이동 아파트");
    expect(u.searchParams.get("v2lng")).toBe("127.098");
    expect(u.searchParams.get("v3lat")).toBeNull();
    expect(u.searchParams.get("slat")).toBeNull(); // 출발은 앱의 현재 위치
    expect(u.searchParams.get("appname")).toBe("https://aucs.co.kr");
    expect(naverRoute([A], "x")).toContain("dname=%EB%B0%A9%EC%9D%B4%EB%8F%99%20"); // 빈칸은 %20
  });
  it("7곳이면 앞 6곳만(경유지 5)", () => {
    const many = Array.from({ length: 7 }, (_, i) => ({ ...A, id: `${i}`, name: `곳${i}` }));
    const u = new URL(naverRoute(many, "x").replace("nmap://", "https://x/"));
    expect(u.searchParams.get("dname")).toBe("곳5");
    expect(u.searchParams.get("v5name")).toBe("곳4");
    expect(u.searchParams.get("v6name")).toBeNull();
  });
  it("안드로이드 intent", () => {
    expect(androidIntent("nmap://route/car?dlat=1")).toBe(
      "intent://route/car?dlat=1#Intent;scheme=nmap;action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;package=com.nhn.android.nmap;end",
    );
  });
});
