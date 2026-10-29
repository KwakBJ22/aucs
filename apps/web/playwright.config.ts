import path from "node:path";
import { loadEnvConfig } from "@next/env";
import { defineConfig } from "@playwright/test";

loadEnvConfig(path.resolve(__dirname, "../..")); // 저장소 맨 위 .env(SUPABASE_URL·SUPABASE_SECRET_KEY — 시험 회원 로그인)

// 핵심 흐름 자동 검사(출시 전 꼭, 10/29) — 켜 둔 화면(3000)·API(8100)를 이 PC의 크롬으로 한 바퀴.
// 실행: scripts\flow-test.ps1 (브라우저를 따로 받지 않고 깔려 있는 크롬을 씀)
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000, // 개발 방식은 화면마다 처음 열 때 몇 초씩 걸림
  expect: { timeout: 20_000 },
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE ?? "http://localhost:3000",
    channel: "chrome",
    locale: "ko-KR",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "휴대폰",
      testMatch: /phone\.spec\.ts/,
      use: { viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true },
    },
    { name: "PC", testMatch: /pc\.spec\.ts/, use: { viewport: { width: 1440, height: 900 } } },
  ],
});
