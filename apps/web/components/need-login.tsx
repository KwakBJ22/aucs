import Link from "next/link";
import { copy } from "@/lib/copy.ko";

export function NeedLogin({ title }: { title: string }) {
  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{title}</div>
      </div>
      <section className="section ta-center py-32 px-18">
        <h2>{copy.needLogin.title}</h2>
        <p className="sub mt-8 mb-20 mx-0">{copy.needLogin.body}</p>
        <Link href="/login" className="btn kakao">
          {copy.home.kakao}
        </Link>
      </section>
    </main>
  );
}
