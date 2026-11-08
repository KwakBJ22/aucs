"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { copy } from "@/lib/copy.ko";

export function NeedLogin({ title }: { title: string }) {
  const here = usePathname(); // 로그인 뒤 이 화면으로 돌아옴
  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{title}</div>
      </div>
      <section className="section ta-center py-32 px-18">
        <h2>{copy.needLogin.title}</h2>
        <p className="sub mt-8 mb-20 mx-0">{copy.needLogin.body}</p>
        <Link href={`/login?next=${encodeURIComponent(here)}`} className="btn kakao">
          {copy.home.kakao}
        </Link>
      </section>
    </main>
  );
}
