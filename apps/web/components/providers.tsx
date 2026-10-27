"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { SessionProvider } from "@/lib/auth";
import { track } from "@/lib/track";

// 화면 이동 기록(주간 재방문·처음 판단까지 시간)
function PageViews() {
  const path = usePathname();
  useEffect(() => {
    if (!path.startsWith("/admin")) track("view");
  }, [path]);
  return null;
}

// 모든 화면이 같이 쓰는 것(로그인 세션)을 맨 위에서 한 번만 준비합니다.
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <PageViews />
      {children}
    </SessionProvider>
  );
}
