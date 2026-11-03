"use client";

import { Delayed, SkLines } from "@/components/skeleton";
import { copyText } from "@/lib/copy-text";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import { Row } from "@/components/calc-box";
import { fetchNotice, type OnbidNotice } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";

const t = copy.onbidNotice;

// 공고문 보기(GM-01): 온비드가 준 공고 칸만. 잔금 기한·특이 조건은 공고 원문에서.
export default function NoticePage() {
  const id = decodeURIComponent(String(useParams().id));
  const [d, setD] = useState<OnbidNotice | null>(null);
  const [failed, setFailed] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchNotice(id)
      .then(setD)
      .catch(() => setFailed(true));
  }, [id]);

  if (failed) return <LoadError onRetry={() => window.location.reload()} />;
  return (
    <main className="page">
      <PageHeader title={t.title} back={`/item/${encodeURIComponent(id)}`} />
      {!d ? (
        <Delayed>
          <section className="section">
            <SkLines n={2} />
          </section>
          <section className="section">
            <SkLines n={8} />
          </section>
        </Delayed>
      ) : (
        <>
          <section className="section">
            <div className="sub m-0">
              {d.mng_no} · {d.kind_name}
            </div>
            <div className="fs-base fw-6 mt-4">{d.title}</div>
          </section>
          <section className="section">
            {d.rows.map((r) => (
              <Row key={r.label} label={r.label} value={r.value} />
            ))}
          </section>
          <section className="section">
            <div className="note blue">{t.checkOriginal}</div>
            <div className="d-flex gap-8 mt-12">
              <button
                className="btn f-1"
                onClick={() =>
                  void copyText(d.mng_no).then(
                    () => setCopied(true),
                    () => setCopied(false),
                  )
                }
              >
                {copied ? copy.onbid.copied : copy.onbid.copyNo}
              </button>
              <a
                className="btn primary f-1"
                href={copy.onbid.onbidUrl}
                target="_blank"
                rel="noreferrer"
              >
                {t.open}
              </a>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
