"use client";

import { NeedLogin } from "@/components/need-login";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

// 전문가 표(전체 물건 · 사건 · 시장 · 지도)는 로그인한 분만(11/17 대표님) — 서버도 로그인 · 이용권을 확인함
export default function ProLayout({ children }: { children: React.ReactNode }) {
  const { session, ready } = useSession();
  if (!ready) return <main className="page" />;
  if (!session) return <NeedLogin title="" body={copy.needLogin.pro} />;
  return children;
}
