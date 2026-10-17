import Link from "next/link";
import { copy } from "@/lib/copy.ko";

const t = copy.more;

export default function More() {
  return (
    <main className="page" style={{ paddingTop: 0 }}>
      <div style={{ background: "var(--surface)", margin: "0 -16px", padding: "24px 20px 20px" }}>
        <div style={{ fontSize: 22, fontWeight: 700 }}>{t.title}</div>
        <div className="sub" style={{ fontSize: 14, marginTop: 8 }}>
          {t.sub}
        </div>
        <Link href="/login" className="btn kakao" style={{ marginTop: 14 }}>
          {copy.home.kakao}
        </Link>
      </div>
      <section className="section" style={{ padding: "4px 18px" }}>
        {t.items.map((name) => (
          <div key={name} className="menu-row">
            <span>{name}</span>
            <span className="sub">{t.soon}</span>
          </div>
        ))}
      </section>
    </main>
  );
}
