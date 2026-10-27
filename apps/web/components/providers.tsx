"use client";

import { SessionProvider } from "@/lib/auth";

// 모든 화면이 같이 쓰는 것(로그인 세션)을 맨 위에서 한 번만 준비합니다.
export function Providers({ children }: { children: React.ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}
