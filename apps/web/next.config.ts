import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// 저장소 맨 위 .env 하나만 씁니다.
loadEnvConfig(path.resolve(__dirname, "../.."));

// 같은 와이파이의 휴대폰에서 개발 화면을 열 때 허용할 주소
const nextConfig: NextConfig = { allowedDevOrigins: ["192.168.*.*", "10.*.*.*"] };

export default nextConfig;
