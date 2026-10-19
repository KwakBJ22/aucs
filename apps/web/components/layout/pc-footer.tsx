import Link from "next/link";
import { copy } from "@/lib/copy.ko";

// PC 바닥: 약관 · 자료 출처 · 고객센터. 휴대폰에서는 CSS로 숨김(전체 탭에 같은 내용).
export function PcFooter() {
  const t = copy.footer;
  return (
    <footer className="pc-footer">
      <div className="pf-grid">
        <div>
          <div className="pf-brand">{copy.appName}</div>
          <div className="pf-links">
            {t.links.map(([name, href]) =>
              href ? (
                <Link key={name} href={href}>
                  {name}
                </Link>
              ) : (
                <span key={name}>{name}</span>
              ),
            )}
          </div>
        </div>
        <div>
          <div className="pf-head">{t.sourceHead}</div>
          {t.sources.map((s) => (
            <div key={s}>{s}</div>
          ))}
        </div>
        <div>
          <div className="pf-head">{t.helpHead}</div>
          <div>{t.help}</div>
          <div>{t.biz}</div>
        </div>
      </div>
      <div className="pf-note">{t.note}</div>
    </footer>
  );
}
