"use client";

import { Delayed, SkLines } from "@/components/skeleton";
import { useEffect, useState } from "react";
import { fetchDocs, type DocKind, type ItemDocs } from "@/lib/api/items";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { t } from "@/components/item/shared";

export function DocH({ children }: { children: React.ReactNode }) {
  return <div className="fs-md fw-7 mt-16 mb-6 mx-0">{children}</div>;
}

export function DocP({ children }: { children: React.ReactNode }) {
  return (
    <p className="fs-md lh-16 m-0" style={{ whiteSpace: "pre-wrap" }}>
      {children}
    </p>
  );
}

// 「이 값이 틀렸어요」 제보(DOC-01): 우리가 뽑은 값이 원문과 다르면 알려 주세요 → 관리자 검증 대기(ADM-01)
export function ReportBox({ id, section }: { id: string; section: string }) {
  const r = t.report;
  const { session } = useSession();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"" | "sending" | "sent" | "fail">("");
  if (state === "sent") return <p className="sub mt-24">{r.thanks}</p>;
  if (!open)
    return (
      <button
        className="btn secondary sm mt-24"
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
    <section className="section mt-24">
      <label className="d-block fs-md fw-6">
        {r.label}
        <textarea
          value={note}
          maxLength={500}
          rows={3}
          placeholder={r.placeholder}
          onChange={(e) => setNote(e.target.value)}
          className="memo-box"
        />
      </label>
      <p className="sub my-6 mx-0">{state === "fail" ? r.fail : r.hint}</p>
      <button className="btn mh-44" disabled={!note.trim() || state === "sending"} onClick={send}>
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
      className="bg-bg oy-auto pt-0 pb-32 px-16"
      style={{ position: "fixed", inset: 0, zIndex: 50 }}
    >
      <div className="topbar pos-sticky bg-bg" style={{ top: 0 }}>
        <b className="fs-lg">{c.names[kind]}</b>
        <button onClick={onClose} className="btn secondary sm">
          {c.close}
        </button>
      </div>
      {docs === undefined && (
        <Delayed>
          <SkLines n={8} />
        </Delayed>
      )}
      {docs?.closed && <p className="sub">{c.closed}</p>}
      {docs !== undefined && !docs?.closed && !cur && <p className="sub">{c.none}</p>}
      {cur && <p className="sub fs-xs mt-0">{c.from(cur.fetched_at)}</p>}
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
                <div key={i} className="fs-md py-6 px-0">
                  <b>{x.name ?? "임차인"}</b> {x.part ?? ""} {x.use ?? ""}
                  <div className="sub m-0">
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
          <div className="d-flex jc-between ai-center">
            <DocH>{c.filings}</DocH>
            <button onClick={() => setAll(!all)} className="link">
              {all ? c.keyOnly : c.all}
            </button>
          </div>
          {dl.filings
            .filter((x) => all || x.key)
            .map((x, i) => (
              <div key={i} className="fs-sm py-4 px-0" style={{ fontWeight: x.key ? 600 : 400 }}>
                <span className="sub m-0">{x.date ?? "-"}</span> {x.text}
                {x.result ? ` · ${x.result}` : ""}
              </div>
            ))}
          {!all && !dl.filings.some((x) => x.key) && <p className="sub">-</p>}
          {all && (
            <>
              <DocH>{c.sends}</DocH>
              {dl.sends.map((x, i) => (
                <div key={i} className="fs-sm py-4 px-0">
                  <span className="sub m-0">{x.date ?? "-"}</span> {x.text}
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
