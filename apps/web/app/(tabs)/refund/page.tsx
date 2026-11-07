import { LegalDoc } from "@/components/legal/legal-doc";
import { copy } from "@/lib/copy.ko";

const t = copy.legal.refund;
export const metadata = { title: `${t.title} · 옥스` };

// 환불 규정(11/7): 이용권별 규칙은 이용권 화면과 같은 문구(copy.plans.refund) 하나를 씀
export default function Page() {
  return (
    <LegalDoc title={t.title}>
      <p className="sub mt-0">{t.intro}</p>
      <div className="legal-item">
        <h2>{t.rulesTitle}</h2>
        <ul>
          {copy.plans.refund.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </div>
      <div className="legal-item">
        <h2>{t.usedTitle}</h2>
        <p>{copy.plans.usedNote}</p>
      </div>
      <div className="legal-item">
        <h2>{t.howTitle}</h2>
        <ul>
          {t.how.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </div>
      <div className="legal-item">
        <h2>{t.lawTitle}</h2>
        <p>{t.law}</p>
      </div>
    </LegalDoc>
  );
}
