import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// 저장소 맨 위 .env 하나만 씁니다.
loadEnvConfig(path.resolve(__dirname, "../.."));

const nextConfig: NextConfig = {};

export default nextConfig;
