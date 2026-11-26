"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminApi, type SpecItem, type SpecSaved } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { errText, useAdmin } from "./ctx";

const t = copy.admin.specGet;

// 명세서 올리기(11/27 대표님): 지난 물건(법원에서 더는 못 받음) 중 매각물건명세서 원본 없는 것 → PDF 올리면 바로 읽음
export function SpecGet() {
  const { token, say } = useAdmin();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<SpecItem[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<Record<string, string>>({});
  const load = (query: string, offset = 0) => {
    setBusy("list");
    adminApi
      .specItems(token, query.trim(), offset)
      .then((r) => {
        setRows((old) => (offset && old ? [...old, ...r.rows] : r.rows));
        setTotal(query.trim() ? null : r.total);
      })
      .catch((e) => say(errText(e)))
      .finally(() => setBusy(null));
  };
  useEffect(() => load(""), []); // eslint-disable-line react-hooks/exhaustive-deps
  const send = (r: SpecItem, f: File | undefined) => {
    if (!f) return;
    setBusy(r.item_id);
    adminApi
      .uploadSpec(token, r.item_id, f)
      .then((s: SpecSaved) => {
        const msg = !s.ok ? t.noText : s.rows || s.none ? t.saved(s.rows, s.none) : t.noTable;
        setDone((d) => ({ ...d, [r.item_id]: msg }));
      })
      .catch((e) => say(errText(e)))
      .finally(() => setBusy(null));
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
          onKeyDown={(e) => e.key === "Enter" && load(q)}
        />
        <button className="adm-btn primary" disabled={busy === "list"} onClick={() => load(q)}>
          {t.go}
        </button>
      </div>
      {total != null && <p className="sub mt-8">{t.total(total)}</p>}
      {rows?.length === 0 && <p className="sub mt-8">{t.none}</p>}
      {rows?.map((r) => (
        <div key={r.item_id} className="adm-card">
          <Link
            prefetch={false}
            href={`/item/${encodeURIComponent(r.item_id)}`}
            target="_blank"
            className="link fw-6"
          >
            {r.address ?? r.item_id}
          </Link>
          <div className="sub mt-2">
            {r.sale_date} · {r.court} {r.case_no} {t.item(r.item_no)}
            {r.usage && ` · ${r.usage}`}
            {r.spec && (
              <span className="chip green ml-6">{r.spec === "court" ? t.court : t.upload}</span>
            )}
          </div>
          <div className="adm-line mt-8">
            <label className="btn soft sm">
              {busy === r.item_id ? t.busy : r.spec ? t.again : t.pick}
              <input
                type="file"
                accept="application/pdf"
                hidden
                disabled={busy === r.item_id}
                onChange={(e) => send(r, e.target.files?.[0])}
              />
            </label>
          </div>
          {done[r.item_id] && <p className="sub fs-sm m-0">{done[r.item_id]}</p>}
        </div>
      ))}
      {total != null && rows && rows.length < total && (
        <button
          className="adm-btn mt-8"
          disabled={busy === "list"}
          onClick={() => load("", rows.length)}
        >
          {t.more}
        </button>
      )}
    </section>
  );
}
