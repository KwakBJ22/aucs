"use client";

import { useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { meApi } from "@/lib/api/me";
import { SessionProvider, useSession } from "@/lib/auth";
import { PROFILE_EVENT, syncProfile } from "@/lib/profile";
import { registerSW } from "@/lib/install";
import { onRouteChange, startScrollMemory } from "@/lib/scroll";
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

// 화면 이동 때 스크롤 한 곳(11/8): 새 화면은 맨 위, #자리는 그 자리, 뒤로 가기는 보던 자리
function ScrollMemory() {
  const path = usePathname();
  useEffect(() => startScrollMemory(), []);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false; // 처음 열 때는 startScrollMemory가 맞춤
      return;
    }
    onRouteChange();
  }, [path]);
  return null;
}

// 서비스 워커는 모든 손님에게(11/8) — 그래야 브라우저가 「앱 설치」를 스스로 띄움(알림 켜기와 같은 파일)
function AppInstall() {
  useEffect(() => registerSW(), []);
  return null;
}

// 오류 기록(10/29): 잡지 못한 화면 오류를 관리자 「오류」로
function ErrorListener() {
  useEffect(() => listenErrors(), []);
  return null;
}

// 로그인하면 이 기기와 계정의 내 조건을 맞춤 — 어느 화면으로 들어와도 한 곳에서(11/8).
// 계정 것을 되살렸으면 그 조건으로 다시 그림(시작 질문 화면이면 홈으로).
function ProfileSync() {
  const { session } = useSession();
  const router = useRouter();
  const path = usePathname();
  const token = session?.access_token;
  useEffect(() => {
    if (!token) return;
    void syncProfile(
      () => meApi.profile(token),
      (b) => meApi.saveProfile(token, b),
    ).then((restored) => {
      if (!restored) return;
      if (path === "/start" || path === "/") router.replace("/home");
      else window.location.reload();
    });
    // 로그인한 동안 조건을 바꾸면(시작 질문·계산 화면) 계정에도 올림
    const push = () =>
      void syncProfile(
        () => Promise.resolve(null),
        (b) => meApi.saveProfile(token, b),
      );
    window.addEventListener(PROFILE_EVENT, push);
    return () => window.removeEventListener(PROFILE_EVENT, push);
    // 로그인할 때 한 번만 맞춤(화면을 옮길 때마다 부르지 않음)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  return null;
}

// 모든 화면이 같이 쓰는 것(로그인 세션)을 맨 위에서 한 번만 준비합니다.
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <PageViews />
      <ErrorListener />
      <AppInstall />
      <ScrollMemory />
      <ProfileSync />
      {children}
    </SessionProvider>
  );
}
