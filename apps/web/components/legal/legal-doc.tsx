import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { copy } from "@/lib/copy.ko";

// 약관·방침 한 장(11/7): 조항 제목 + 본문. 고객센터로 가는 줄을 맨 아래에.
export function LegalDoc({
  title,
  sections,
  children,
}: {
  title: string;
  sections?: readonly (readonly [string, string])[];
  children?: React.ReactNode;
}) {
  return (
    <main className="page narrow">
      <PageHeader title={title} back="/more" />
      <p className="sub mt-0">{copy.legal.draft("2026-11-07")}</p>
      <section className="section legal">
        {sections?.map(([h, p]) => (
          <div key={h} className="legal-item">
            <h2>{h}</h2>
            <p>{p}</p>
          </div>
        ))}
        {children}
      </section>
      <Link href="/help" className="menu-row">
        <span>{copy.help.title}</span>
        <span className="sub">›</span>
      </Link>
    </main>
  );
}
