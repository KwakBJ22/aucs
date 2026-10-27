"use client";

import { useEffect, useState } from "react";
import { fetchDocs, type DocKind, type ItemDocs } from "@/lib/api/items";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { t } from "@/components/item/shared";

export function DocH({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 14, fontWeight: 700, margin: "16px 0 6px" }}>{children}</div>;
}

export function DocP({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ fontSize: 14, lineHeight: 1.6, margin: 0, whiteSpace: "pre-wrap" }}>{children}</p>
  );
}

// 「이 값이 틀렸어요」 제보(DOC-01): 우리가 뽑은 값이 원문과 다르면 알려 주세요 → 관리자 검증 대기(ADM-01)
export function ReportBox({ id, section }: { id: string; section: string }) {
  const r = t.report;
  const { session } = useSession();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"" | "sending" | "sent" | "fail">("");
  if (state === "sent")
    return (
      <p className="sub" style={{ marginTop: 24 }}>
        {r.thanks}
      </p>
    );
  if (!open)
    return (
      <button
        className="chip gray"
        style={{ border: 0, minHeight: 40, marginTop: 24 }}
        onClick={() => (session ? setOpen(true) : (window.location.href = "/login"))}
      >
        {r.open}
      </button>
    );
  const send = () => {
    if (!session || !note.trim()) return;
    setState("sending");
    meApi
      .report(session.access_token, { item_id: id, section, note: note.trim() })
      .then(() => setState("sent"))
      .catch(() => setState("fail"));
  };
  return (
    <section className="section" style={{ marginTop: 24 }}>
      <label style={{ display: "block", fontSize: 14, fontWeight: 600 }}>
        {r.label}
        <textarea
          value={note}
          maxLength={500}
          rows={3}
          placeholder={r.placeholder}
          onChange={(e) => setNote(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 6, fontSize: 15, padding: 8 }}
        />
      </label>
      <p className="sub" style={{ margin: "6px 0" }}>
        {state === "fail" ? r.fail : r.hint}
      </p>
      <button
        className="btn"
        disabled={!note.trim() || state === "sending"}
        onClick={send}
        style={{ minHeight: 44 }}
      >
        {r.send}
      </button>
    </section>
  );
}

export function DocSheet({
  id,
  kind,
  onClose,
}: {
  id: string;
  kind: DocKind;
  onClose: () => void;
}) {
  const c = t.doc;
  const [docs, setDocs] = useState<ItemDocs | null | undefined>(undefined);
  const [all, setAll] = useState(false);
  useEffect(() => {
    fetchDocs(id)
      .then(setDocs)
      .catch(() => setDocs(null));
  }, [id]);
  const sr = docs?.status_report;
  const dl = docs?.deliveries;
  const sp = docs?.spec_sheet;
  const cur = kind === "status_report" ? sr : kind === "deliveries" ? dl : sp;
  return (
    <div
      role="dialog"
      aria-label={c.names[kind]}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "var(--bg, #fff)",
        overflowY: "auto",
        padding: "0 16px 32px",
      }}
    >
      <div className="topbar" style={{ position: "sticky", top: 0, background: "var(--bg, #fff)" }}>
        <b style={{ fontSize: 17 }}>{c.names[kind]}</b>
        <button
          onClick={onClose}
          style={{ border: 0, background: "none", fontSize: 15, minWidth: 44, minHeight: 44 }}
        >
          {c.close}
        </button>
      </div>
      {docs === undefined && <p className="sub">{c.loading}</p>}
      {docs !== undefined && !cur && <p className="sub">{c.none}</p>}
      {cur && (
        <p className="sub" style={{ fontSize: 12, marginTop: 0 }}>
          {c.from(cur.fetched_at)}
        </p>
      )}
      {kind === "status_report" && sr && (
        <>
          {sr.exam_at && (
            <>
              <DocH>{c.examAt}</DocH>
              <DocP>{sr.exam_at}</DocP>
            </>
          )}
          {sr.summary && (
            <>
              <DocH>{c.summary}</DocH>
              <DocP>{sr.summary}</DocP>
            </>
          )}
          {sr.possession.length > 0 && (
            <>
              <DocH>{c.possession}</DocH>
              {sr.possession.map((x, i) => (
                <DocP key={i}>{x}</DocP>
              ))}
            </>
          )}
          {sr.lease_note && (
            <>
              <DocH>{c.leaseNote}</DocH>
              <DocP>{sr.lease_note}</DocP>
            </>
          )}
          {sr.tenants.length > 0 && (
            <>
              <DocH>{c.tenants}</DocH>
              {sr.tenants.map((x, i) => (
                <div
                  key={i}
                  style={{ fontSize: 14, padding: "6px 0", borderBottom: "1px solid var(--line)" }}
                >
                  <b>{x.name ?? "임차인"}</b> {x.part ?? ""} {x.use ?? ""}
                  <div className="sub" style={{ margin: 0 }}>
                    {[
                      x.move_in && `전입 ${x.move_in}`,
                      x.fixed && `확정 ${x.fixed}`,
                      x.deposit && `보증금 ${x.deposit}`,
                      x.rent && `차임 ${x.rent}`,
                      x.note,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "-"}
                  </div>
                </div>
              ))}
            </>
          )}
        </>
      )}
      {kind === "spec_sheet" && sp && (
        <>
          {(
            [
              [c.written, sp.written],
              [c.base, sp.base],
              [c.keep, sp.keep],
              [c.superficies, sp.superficies],
              [c.remark, [sp.remark, sp.item_remark].filter(Boolean).join("\n")],
            ] as [string, string | null][]
          )
            .filter(([, v]) => v)
            .map(([h, v]) => (
              <div key={h}>
                <DocH>{h}</DocH>
                <DocP>{v}</DocP>
              </div>
            ))}
        </>
      )}
      {kind === "deliveries" && dl && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <DocH>{c.filings}</DocH>
            <button
              onClick={() => setAll(!all)}
              style={{
                border: 0,
                background: "none",
                color: "var(--blue)",
                fontSize: 13,
                minHeight: 44,
              }}
            >
              {all ? c.keyOnly : c.all}
            </button>
          </div>
          {dl.filings
            .filter((x) => all || x.key)
            .map((x, i) => (
              <div
                key={i}
                style={{ fontSize: 13, padding: "4px 0", fontWeight: x.key ? 600 : 400 }}
              >
                <span className="sub" style={{ margin: 0 }}>
                  {x.date ?? "-"}
                </span>{" "}
                {x.text}
                {x.result ? ` · ${x.result}` : ""}
              </div>
            ))}
          {!all && !dl.filings.some((x) => x.key) && <p className="sub">-</p>}
          {all && (
            <>
              <DocH>{c.sends}</DocH>
              {dl.sends.map((x, i) => (
                <div key={i} style={{ fontSize: 13, padding: "4px 0" }}>
                  <span className="sub" style={{ margin: 0 }}>
                    {x.date ?? "-"}
                  </span>{" "}
                  {x.text}
                  {x.result ? ` · ${x.result}` : ""}
                </div>
              ))}
            </>
          )}
        </>
      )}
      <ReportBox id={id} section={c.names[kind] ?? kind} />
    </div>
  );
}
