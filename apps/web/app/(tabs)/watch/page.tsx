import { NeedLogin } from "@/components/need-login";
import { copy } from "@/lib/copy.ko";

export default function Watch() {
  return <NeedLogin title={copy.tabs.watch} />;
}
