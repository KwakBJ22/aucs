"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import { createContext, createElement, useContext, useEffect, useState } from "react";
import { clearMeCache } from "@/lib/api/client";

// 로그인은 Supabase Auth (이메일 링크, 카카오는 키를 받으면 추가). 공개 키만 씁니다.
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
    options: { emailRedirectTo: `${window.location.origin}/home` },
  });
  return error ? error.message : null;
}

export async function signOut(): Promise<void> {
  clearMeCache();
  await supabase?.auth.signOut();
}
