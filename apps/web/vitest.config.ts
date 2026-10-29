import { defineConfig } from "vitest/config";

// 단위 시험만(lib/*.test.ts). e2e/ 는 Playwright(scripts\flow-test.ps1)
export default defineConfig({
  test: { exclude: ["e2e/**", "node_modules/**", ".next/**", ".next-fast/**"] },
});
