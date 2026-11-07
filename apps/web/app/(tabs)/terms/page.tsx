import { LegalDoc } from "@/components/legal/legal-doc";
import { copy } from "@/lib/copy.ko";

export const metadata = { title: `${copy.legal.terms.title} · 옥스` };

export default function Page() {
  return <LegalDoc title={copy.legal.terms.title} sections={copy.legal.terms.sections} />;
}
