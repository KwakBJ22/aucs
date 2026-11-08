"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import { SkDetail } from "@/components/skeleton";
import { isNotFound } from "@/lib/api/client";
import {
  requestDocs,
  fetchItem,
  isOnbid,
  type DocKind,
  type ItemDetail,
  type OnbidDetail,
} from "@/lib/api/items";
import { rememberItem } from "@/lib/recent";
import { track } from "@/lib/track";
import { useIsPc } from "@/lib/use-pc";
import { useParams } from "next/navigation";
import { DocSheet } from "@/components/item/doc-sheet";
import { OnbidItem } from "@/components/item/onbid-detail";
import { ItemView } from "@/components/item/item-view";
import { RegCtx, useMyRegistry } from "@/components/item/registry";
import { t, DocCtx } from "@/components/item/shared";

export default function Item() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<ItemDetail | null | undefined>(undefined);
  const reg = useMyRegistry(decodeURIComponent(id));
  const [doc, setDoc] = useState<DocKind | null>(null);
  const pc = useIsPc();

  const [failed, setFailed] = useState(false);
  const [tries, setTries] = useState(0);
  useEffect(() => {
    setFailed(false);
    fetchItem(decodeURIComponent(id))
      .then((x) => {
        setD(x);
        track("item_view", x.item_id);
        // 현황조사가 아직 없으면 서류 받기를 줄 세움(11/4) — 손님이 본 물건부터 「자료 기다림」이 채워짐
        if (!isOnbid(x) && !x.tags?.find((g) => g.label === "현황조사")?.ok) requestDocs(x.item_id);
        rememberItem(
          x.item_id,
          `${isOnbid(x) ? "공매" : x.court} ${x.case_no} · ${x.place} ${x.building ?? x.usage ?? ""}`,
        );
      })
      .catch((e: unknown) => (isNotFound(e) ? setD(null) : setFailed(true)));
  }, [id, tries]);

  if (failed && d === undefined)
    return (
      <main className="page">
        <PageHeader title="" back="history" />
        <LoadError onRetry={() => setTries((n) => n + 1)} />
      </main>
    );
  if (d === undefined)
    return (
      <main className="page">
        <div className="topbar" />
        <SkDetail />
      </main>
    );
  if (d === null)
    return (
      <main className="page">
        <p className="sub p-24">{t.notFound}</p>
      </main>
    );
  if (isOnbid(d)) return <OnbidItem d={d as unknown as OnbidDetail} />; // 공매(10/28)
  // 휴대폰·PC 한 벌(11/8) — 배치만 pc 로 나눔
  return (
    <RegCtx.Provider value={reg}>
      <DocCtx.Provider value={setDoc}>
        <ItemView d={d} reg={reg} pc={pc} />
        {doc && <DocSheet id={d.item_id} kind={doc} onClose={() => setDoc(null)} />}
      </DocCtx.Provider>
    </RegCtx.Provider>
  );
}
