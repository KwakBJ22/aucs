"use client";

import { NeedLogin } from "@/components/need-login";
import { SkDetail } from "@/components/skeleton";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

// 물건 상세(계산·입찰표·보고서 등 그 아래 화면 모두)는 로그인한 분만(11/12 대표님) — 로그인 뒤 이 물건으로 돌아옴
export default function ItemLayout({ children }: { children: React.ReactNode }) {
  const { session, ready } = useSession();
  if (!ready)
    return (
      <main className="page">
        <div className="topbar" />
        <SkDetail />
      </main>
    );
  if (!session) return <NeedLogin title="" body={copy.needLogin.item} />;
  return children;
}
