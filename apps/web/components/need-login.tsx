import Link from "next/link";
import { copy } from "@/lib/copy.ko";

export function NeedLogin({ title }: { title: string }) {
  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{title}</div>
      </div>
      <section className="section" style={{ textAlign: "center", padding: "32px 18px" }}>
        <h2>{copy.needLogin.title}</h2>
        <p className="sub" style={{ margin: "8px 0 20px" }}>
          {copy.needLogin.body}
        </p>
        <Link href="/login" className="btn kakao">
          {copy.home.kakao}
        </Link>
      </section>
    </main>
  );
}
