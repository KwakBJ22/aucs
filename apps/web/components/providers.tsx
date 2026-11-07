"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { meApi } from "@/lib/api/me";
import { SessionProvider, useSession } from "@/lib/auth";
import { pushProfile } from "@/lib/profile";
import { listenErrors } from "@/lib/report-error";
import { track } from "@/lib/track";

// 화면 이동 기록(주간 재방문·처음 판단까지 시간)
function PageViews() {
  const path = usePathname();
  useEffect(() => {
    if (!path.startsWith("/admin")) track("view");
  }, [path]);
  return null;
}

// 오류 기록(10/29): 잡지 못한 화면 오류를 관리자 「오류」로
function ErrorListener() {
  useEffect(() => listenErrors(), []);
  return null;
}

// 로그인하면 시작 질문 답(내 조건)을 계정에 옮겨 둠 — 어느 화면으로 들어와도 한 곳에서(11/8)
function ProfileSync() {
  const { session } = useSession();
  const token = session?.access_token;
  useEffect(() => {
    if (token) pushProfile(token, (b) => meApi.saveProfile(token, b));
  }, [token]);
  return null;
}

// 모든 화면이 같이 쓰는 것(로그인 세션)을 맨 위에서 한 번만 준비합니다.
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <PageViews />
      <ErrorListener />
      <ProfileSync />
      {children}
    </SessionProvider>
  );
}
