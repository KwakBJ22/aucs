import { LegalDoc } from "@/components/legal/legal-doc";
import { copy } from "@/lib/copy.ko";

export const metadata = { title: `${copy.legal.privacy.title} · 옥스` };

export default function Page() {
  return <LegalDoc title={copy.legal.privacy.title} sections={copy.legal.privacy.sections} />;
}
