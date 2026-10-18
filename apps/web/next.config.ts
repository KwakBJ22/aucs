import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// 저장소 맨 위 .env 하나만 씁니다.
loadEnvConfig(path.resolve(__dirname, "../.."));

// 맨 위 .env 의 NEXT_PUBLIC_* 값을 화면 코드에 확실히 넣음 (loadEnvConfig 만으로는 안 들어갔음, 10/18)
const publicEnv = Object.fromEntries(
  Object.entries(process.env).filter(([k, v]) => k.startsWith("NEXT_PUBLIC_") && v),
) as Record<string, string>;

const nextConfig: NextConfig = {
  env: publicEnv,
  // 같은 와이파이의 휴대폰에서 개발 화면을 열 때 허용할 주소
  allowedDevOrigins: ["192.168.*.*", "10.*.*.*"],
};

export default nextConfig;
