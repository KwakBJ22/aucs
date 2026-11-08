"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import { createContext, createElement, useContext, useEffect, useState } from "react";
import { clearMeCache } from "@/lib/api/client";

// 로그인은 Supabase Auth (카카오 · 이메일 링크, 11/8 카카오 열림). 공개 키만 씁니다.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
export const supabase = url && key ? createClient(url, key) : null;

type SessionState = { session: Session | null; ready: boolean };
const Ctx = createContext<SessionState | null>(null);

// 10/27 속도 개선: 예전엔 머리·화면·관심 하트·계산 상자가 각자 세션을 읽고 구독해(한 화면 4~5번)
// 토큰이 같아도 세션 객체가 바뀔 때마다 화면들이 자료를 다시 불렀음.
// 이제 맨 위에서 한 번만 읽고, 토큰이 실제로 바뀔 때만 새 값으로 바꿉니다.
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SessionState>({ session: null, ready: !supabase });
  useEffect(() => {
    if (!supabase) return;
    const put = (s: Session | null) =>
      setState((cur) =>
        cur.ready && cur.session?.access_token === s?.access_token
          ? cur
          : { session: s, ready: true },
      );
    supabase.auth.getSession().then(({ data }) => put(data.session));
    const { data } = supabase.auth.onAuthStateChange((_e, s) => {
      if (!s) clearMeCache();
      put(s);
    });
    return () => data.subscription.unsubscribe();
  }, []);
  return createElement(Ctx.Provider, { value: state }, children);
}

export function useSession(): SessionState {
  const v = useContext(Ctx);
  if (!v) throw new Error("SessionProvider 밖에서 useSession을 썼어요");
  return v;
}

export async function sendLoginLink(email: string): Promise<string | null> {
  if (!supabase) return "로그인 설정이 아직 없어요";
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: `${window.location.origin}${nextPath()}` },
  });
  return error ? error.message : null;
}

// 로그인 뒤 돌아갈 곳: /login?next=/item/... 처럼 받은 우리 사이트 안 주소만(밖으로 새지 않게)
export function nextPath(): string {
  const n = new URLSearchParams(window.location.search).get("next") ?? "";
  return n.startsWith("/") && !n.startsWith("//") ? n : "/home";
}

export async function signInWithKakao(): Promise<string | null> {
  if (!supabase) return "로그인 설정이 아직 없어요";
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "kakao",
    options: { redirectTo: `${window.location.origin}${nextPath()}` },
  });
  return error ? error.message : null;
}

// 화면에 보일 회원 이름: 이메일이 없으면 카카오 닉네임
export function userLabel(s: Session): string {
  const m = s.user.user_metadata ?? {};
  return s.user.email || m.name || m.full_name || m.nickname || m.preferred_username || "";
}

export async function signOut(): Promise<void> {
  clearMeCache();
  await supabase?.auth.signOut();
}
