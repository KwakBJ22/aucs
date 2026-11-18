"use client";

import Link from "next/link";
import { useState } from "react";
import { DDay } from "@/components/dday";
import { AppraisalUpload } from "@/components/item/appraisal";
import { RegCtx, RegistryBox, useMyRegistry } from "@/components/item/registry";
import { adminApi, type CaseItem } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { parseTime } from "@/lib/format";
import { errText, useAdmin } from "./ctx";

const t = copy.admin.upload;
const dDay = (iso: string | null) =>
  iso ? Math.round((parseTime(iso).getTime() - new Date().setHours(0, 0, 0, 0)) / 864e5) : null;

// 서류 올리기(11/18 대표님): 사건번호로 물건을 찾아, 손님 물건 화면과 같은 칸으로 감정평가서 · 등기부를 올림(포인트 없음)
export function DocUpload() {
  const { token, say } = useAdmin();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<CaseItem[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const find = () => {
    if (!q.trim()) return;
    setBusy(true);
    adminApi
      .caseItems(token, q.trim())
      .then((x) => {
        setRows(x);
        setOpen(x.length === 1 ? x[0].item_id : null);
      })
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
        <div key={r.item_id} className="adm-card">
          <button
            className="link fw-6 ta-left"
            onClick={() => setOpen(open === r.item_id ? null : r.item_id)}
          >
            {r.address ?? r.item_id}
          </button>
          <div className="sub mt-2">
            <DDay d={dDay(r.sale_date)} /> · {r.court} {r.case_no} {t.item(r.item_no)}
            {r.usage && ` · ${r.usage}`}
            {r.has_appraisal && <span className="chip green ml-6">{t.hasAppraisal}</span>}{" "}
            <Link
              prefetch={false}
              href={`/item/${encodeURIComponent(r.item_id)}`}
              target="_blank"
              className="link ml-6"
            >
              ↗
            </Link>
          </div>
          {open === r.item_id && <Uploads r={r} />}
        </div>
      ))}
    </section>
  );
}

// 펼친 물건 하나만 서버에 물음(물건마다 올린 서류 확인 2번)
function Uploads({ r }: { r: CaseItem }) {
  const reg = useMyRegistry(r.item_id);
  return (
    <div className="mt-8">
      <div className="fs-md fw-7 mt-8">{t.appraisal}</div>
      {r.has_appraisal ? (
        <span className="chip green mt-6">{t.hasAppraisal}</span>
      ) : (
        <AppraisalUpload itemId={r.item_id} admin />
      )}
      <div className="fs-md fw-7 mt-12">{t.registry}</div>
      <RegCtx.Provider value={reg}>
        <RegistryBox admin />
      </RegCtx.Provider>
    </div>
  );
}
