"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DDay } from "@/components/dday";
import { OriginalLink } from "@/components/item/appraisal";
import { adminApi, type CaseItem } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { parseTime } from "@/lib/format";
import { IROS_HOME } from "@/lib/go-links";
import { errText, useAdmin } from "./ctx";

const t = copy.admin.docsGet;
const dDay = (iso: string | null) =>
  iso ? Math.round((parseTime(iso).getTime() - new Date().setHours(0, 0, 0, 0)) / 864e5) : null;

// 서류 받기(11/24 대표님): 사건번호로 찾아 감정평가서(법원) · 등기부등본(인터넷등기소)을 받음.
// 받은 PDF 는 다운로드 폴더에 두면 PC 가 감정평가서 · 등기부등본 폴더로 옮겨 알아서 올림
export function DocsGet() {
  const { token, say } = useAdmin();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<CaseItem[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  // 복사 뒤 2초 동안만 단추 글자를 「복사함」으로
  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => setCopied(null), 2000);
    return () => window.clearTimeout(id);
  }, [copied]);
  const find = () => {
    if (!q.trim()) return;
    setBusy(true);
    adminApi
      .caseItems(token, q.trim())
      .then(setRows)
      .catch((e) => say(errText(e)))
      .finally(() => setBusy(false));
  };
  return (
    <section className="section">
      <p className="sub">{t.note}</p>
      <div className="adm-line">
        <input
          className="adm-input"
          placeholder={t.ask}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && find()}
        />
        <button className="adm-btn primary" disabled={busy} onClick={find}>
          {t.go}
        </button>
      </div>
      {rows?.length === 0 && <p className="sub mt-8">{t.none}</p>}
      {rows?.map((r) => (
        <div key={r.item_id} className="adm-card adm-item">
          <Link
            prefetch={false}
            href={`/item/${encodeURIComponent(r.item_id)}`}
            target="_blank"
            className="link fw-6 adm-item-addr"
          >
            {r.address ?? r.item_id}
          </Link>
          <div className="sub adm-item-info">
            <DDay d={dDay(r.sale_date)} /> · {r.court} {r.case_no} {t.item(r.item_no)}
            {r.usage && ` · ${r.usage}`}
            {r.has_appraisal && <span className="chip green ml-6">{t.hasAppraisal}</span>}
          </div>
          <div className="adm-item-btns">
            {!r.has_appraisal && <OriginalLink court={r.court} caseNo={r.case_no} compact />}
            <a
              className="btn soft sm"
              href={IROS_HOME}
              target="_blank"
              rel="noreferrer"
              onClick={() => {
                if (!r.address) return;
                navigator.clipboard?.writeText(r.address).then(
                  () => setCopied(r.item_id),
                  () => setCopied(null),
                );
              }}
            >
              {copied === r.item_id ? t.copied : t.registry}
            </a>
          </div>
        </div>
      ))}
    </section>
  );
}
