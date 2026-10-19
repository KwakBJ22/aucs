"use client";

import { useParams } from "next/navigation";
import { NeedLogin } from "@/components/need-login";
import { PageHeader } from "@/components/layout/page-header";
import { WorkspacePanel } from "@/components/workspace-panel";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { useIsPc } from "@/lib/use-pc";

// 물건 작업 공간(WATCH-02): 휴대폰은 탭 4개, PC는 전부 펼침
export default function WorkspacePage() {
  const id = decodeURIComponent(String(useParams().id));
  const { session, ready } = useSession();
  const pc = useIsPc();
  if (!ready) return null;
  if (!session) return <NeedLogin title={copy.ws.title} />;
  return (
    <main className={pc ? "page narrow" : "page"}>
      <PageHeader title={copy.ws.title} back="/watch" />
      <WorkspacePanel id={id} token={session.access_token} all={pc} />
    </main>
  );
}
