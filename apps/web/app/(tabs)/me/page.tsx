import { NeedLogin } from "@/components/need-login";
import { copy } from "@/lib/copy.ko";

export default function Me() {
  return <NeedLogin title={copy.tabs.me} />;
}
