"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { HeartButton } from "@/components/heart-button";
import { useWatch } from "@/components/watch-context";
import {
  fetchDocs,
  fetchItem,
  type DocKind,
  type ItemDocs,
  type ItemDetail,
  type Question,
} from "@/lib/api/items";
import { meApi, uploadRegistry, type RegistryUpload } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { useIsPc } from "@/lib/use-pc";
import { CalcBox, Row } from "@/components/calc-box";
import { LoadError } from "@/components/load-error";
import { isNotFound } from "@/lib/api/client";
import { rememberItem } from "@/lib/recent";
import { PageHeader } from "@/components/layout/page-header";

const t = copy.item;
const DOT: Record<Question["tone"], string> = {
  green: "var(--green)",
  gray: "var(--faint)",
  orange: "var(--amber)",
  red: "var(--red)",
  blue: "var(--blue)",
};

const JUDGE_COLOR: Record<string, string> = {
  인수: "var(--red)",
  말소기준: "var(--blue)",
  "확인 필요": "var(--amber)",
};

// 등기부 올리기 + 권리 사다리(ITEM-03). 올린 사람만 봄.
// DOC-01 원문 보기: 화면 전체로 올라오는 창 (처음 열 때 한 번 불러옴)
const DocCtx = createContext<(k: DocKind) => void>(() => {});

function DocH({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 14, fontWeight: 700, margin: "16px 0 6px" }}>{children}</div>;
}
function DocP({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ fontSize: 14, lineHeight: 1.6, margin: 0, whiteSpace: "pre-wrap" }}>{children}</p>
  );
}

// 「이 값이 틀렸어요」 제보(DOC-01): 우리가 뽑은 값이 원문과 다르면 알려 주세요 → 관리자 검증 대기(ADM-01)
function ReportBox({ id, section }: { id: string; section: string }) {
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

function DocSheet({ id, kind, onClose }: { id: string; kind: DocKind; onClose: () => void }) {
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

// 내가 올린 등기부: 상세 화면 전체가 같이 씀(「무엇을 떠안나」 요약 줄도 이걸로 바뀜)
type MyReg = {
  ready: boolean;
  token?: string;
  u: RegistryUpload | null | undefined;
  err: string | null;
  sending: boolean;
  startedAt: number | null;
  pick: (f: File | undefined) => void;
  fix: (section: string, rank_no: string, purpose: string) => void;
  accept: () => void;
};
const RegCtx = createContext<MyReg | null>(null);

function useMyRegistry(id: string): MyReg {
  const { session, ready } = useSession();
  const token = session?.access_token;
  const [u, setU] = useState<RegistryUpload | null | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);
  const [round, setRound] = useState(0); // 올릴 때마다 다시 확인 시작
  const [sending, setSending] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);

  useEffect(() => {
    if (!token) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () =>
      meApi
        .registry(token, id)
        .then((x) => {
          if (stop) return;
          setU(x);
          if (x?.status === "processing") {
            // 이 화면을 떠났다 돌아와도 올린 시각부터 막대를 이어 감
            setStartedAt((v) => v ?? (x.created_at ? Date.parse(x.created_at) : Date.now()));
            timer = setTimeout(load, 3000);
          } else setStartedAt(null);
        })
        .catch(() => !stop && setU(null));
    load();
    return () => {
      stop = true;
      if (timer) clearTimeout(timer);
    };
  }, [token, id, round]);

  const pick = useCallback(
    (f: File | undefined) => {
      if (!f || !token) return;
      setErr(null);
      setSending(true);
      setStartedAt(Date.now());
      setU((v) => ({ ...(v ?? ({} as RegistryUpload)), status: "processing", ladder: null }));
      uploadRegistry(token, id, f)
        .then(() => setRound((n) => n + 1))
        .catch((e: Error) => {
          setErr(e.message);
          setStartedAt(null);
          setRound((n) => n + 1);
        })
        .finally(() => setSending(false));
    },
    [token, id],
  );
  const fix = useCallback(
    (section: string, rank_no: string, purpose: string) => {
      if (!token) return;
      meApi
        .fixRight(token, id, { section, rank_no, purpose })
        .then(setU)
        .catch((e: Error) => setErr(e.message));
    },
    [token, id],
  );
  const accept = useCallback(() => {
    if (!token) return;
    meApi
      .acceptAddress(token, id)
      .then(setU)
      .catch((e: Error) => setErr(e.message));
  }, [token, id]);
  return { ready, token, u, err, sending, startedAt, pick, fix, accept };
}

// 읽는 동안 진행 막대: 서버가 페이지별 진행을 알려 주지 않아 시간 기준(그림 PDF 약 40초).
// 결과가 오기 전엔 90%에서 기다리고, 오면 막대가 사라지고 결과가 나옴.
const EXPECT_SEC = 40;
function ReadingBar({ sending, startedAt }: { sending: boolean; startedAt: number | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(iv);
  }, []);
  const sec = startedAt ? Math.max(0, (now - startedAt) / 1000) : 0;
  const pct = sending ? Math.min(15, 5 + sec * 3) : Math.min(90, 15 + (75 * sec) / EXPECT_SEC);
  const step = sending ? 0 : pct < 75 ? 1 : 2;
  const r = t.reg;
  return (
    <div role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
        <b>{r.reading}</b>
        <span className="sub" style={{ margin: 0 }}>
          {r.left(Math.round(EXPECT_SEC - sec))}
        </span>
      </div>
      <div style={{ height: 8, borderRadius: 4, background: "var(--line)", marginTop: 8 }}>
        <div
          style={{
            width: `${pct}%`,
            height: 8,
            borderRadius: 4,
            background: "var(--blue)",
            transition: "width .5s linear",
          }}
        />
      </div>
      <div style={{ display: "flex", gap: 12, fontSize: 12, marginTop: 6 }}>
        {r.steps.map((s, i) => (
          <span
            key={s}
            style={{ color: i < step ? "var(--blue)" : i === step ? "inherit" : "var(--faint)" }}
          >
            {i + 1} {s}
            {i < step ? " ✓" : i === step ? " …" : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

function PayoutBox({ p }: { p: NonNullable<RegistryUpload["ladder"]>["payout"] & object }) {
  const [open, setOpen] = useState(false);
  const r = t.reg;
  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          border: 0,
          background: "none",
          padding: "8px 0",
          minHeight: 44,
          fontSize: 14,
          fontWeight: 600,
          color: "inherit",
        }}
      >
        {r.payTitle(won(p.price_krw))} {open ? "⌃" : "›"}
      </button>
      {open && (
        <>
          {p.rows.map((x, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 8,
                fontSize: 13,
                padding: "3px 0",
                color: x.paid_krw ? "inherit" : "var(--muted)",
              }}
            >
              <span>
                {i + 1}. {x.name}
              </span>
              <span style={{ whiteSpace: "nowrap" }}>
                {won(x.paid_krw)}
                {x.claim_krw && x.claim_krw > x.paid_krw ? ` / ${won(x.claim_krw)}` : ""}
              </span>
            </div>
          ))}
          {p.surplus_krw > 0 && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 13,
                padding: "3px 0",
              }}
            >
              <span>{r.payLeft}</span>
              <span>{won(p.surplus_krw)}</span>
            </div>
          )}
          {p.unknown.length > 0 && (
            <p style={{ fontSize: 12, color: "var(--amber)", margin: "6px 0 0" }}>
              {r.payUnknown(p.unknown.join(", "))}
            </p>
          )}
          <p className="sub" style={{ fontSize: 12, margin: "4px 0 0" }}>
            {r.payNote}
          </p>
        </>
      )}
    </div>
  );
}

function RegistryBox() {
  const r = t.reg;
  const reg = useContext(RegCtx);
  const pc = useIsPc();
  const [ladOpen, setLadOpen] = useState(false);
  if (!reg || !reg.ready) return null;
  const { token, u, err, pick, fix, accept, sending, startedAt } = reg;
  const addr = u?.status === "parsed" ? u.address : undefined;
  const blocked =
    !!addr && !addr.ok && (addr.result === "different" || addr.result === "unit_differs");
  if (!token)
    return (
      <p className="sub" style={{ marginTop: 10 }}>
        {r.needLogin}
      </p>
    );
  const lad = u?.ladder;
  return (
    <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
      {u?.status === "processing" && <ReadingBar sending={sending} startedAt={startedAt} />}
      {blocked && addr && (
        <div style={{ border: "1px solid var(--amber)", borderRadius: 12, padding: 12 }}>
          <b style={{ color: "var(--amber)", fontSize: 15 }}>
            {addr.result === "unit_differs" && addr.registry_unit && addr.item_unit
              ? r.addrUnit(addr.registry_unit, addr.item_unit)
              : r.addrDiff}
          </b>
          <div style={{ fontSize: 13, marginTop: 8, lineHeight: 1.5 }}>
            <div>
              <span className="sub" style={{ margin: 0 }}>
                {r.addrReg}
              </span>{" "}
              {addr.registry}
            </div>
            <div>
              <span className="sub" style={{ margin: 0 }}>
                {r.addrItem}
              </span>{" "}
              {addr.item}
            </div>
          </div>
          <button
            onClick={accept}
            style={{
              border: 0,
              background: "none",
              color: "var(--muted)",
              fontSize: 13,
              padding: "10px 0 0",
              minHeight: 44,
            }}
          >
            {r.addrStill} ›
          </button>
        </div>
      )}
      {lad && addr?.result === "unknown" && (
        <p style={{ fontSize: 13, color: "var(--amber)", margin: "0 0 6px" }}>{r.addrUnknown}</p>
      )}
      {u?.status === "failed" && <p style={{ color: "var(--amber)", fontSize: 14 }}>{r.failed}</p>}
      {lad && (
        <>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{lad.line}</div>
          {lad.spec_check && (
            <div
              style={{
                fontSize: 12,
                marginTop: 4,
                color: lad.spec_check.same ? "var(--muted)" : "var(--amber)",
                fontWeight: lad.spec_check.same ? 400 : 600,
              }}
            >
              {lad.spec_check.same
                ? r.specSame(lad.spec_check.spec)
                : r.specDiff(lad.spec_check.spec, lad.spec_check.registry_date)}
            </div>
          )}
          {!pc && (
            <button
              className="cond-row"
              style={{ background: "var(--bg)" }}
              onClick={() => setLadOpen(!ladOpen)}
            >
              <span>
                <b>
                  {r.foldTitle(
                    lad.rows.length,
                    lad.rows.filter((x) => x.judgment !== "소멸").length,
                  )}
                </b>
                {lad.base && (
                  <span className="sub" style={{ display: "block" }}>
                    {r.foldBase(lad.base.name, lad.base.date ?? "")}
                  </span>
                )}
              </span>
              <span className="sub">{ladOpen ? "▴" : "›"}</span>
            </button>
          )}
          <div style={{ marginTop: 6, display: pc || ladOpen ? "block" : "none" }}>
            {lad.rows.map((x) => (
              <div key={`${x.section}${x.rank_no}`}>
                {x.is_base && lad.base && (
                  <div style={{ fontSize: 12, color: "var(--blue)", padding: "6px 0" }}>
                    {r.baseLine(lad.base.name, lad.base.date ?? "")}
                  </div>
                )}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 8,
                    fontSize: 13,
                    padding: "4px 0",
                    color: x.judgment === "소멸" ? "var(--muted)" : "inherit",
                  }}
                >
                  <span>
                    {x.date ?? "-"} · {x.name}
                    {x.mark ? <span style={{ color: "var(--muted)" }}> ({x.mark})</span> : null}
                    {x.holder ? ` · ${x.holder}` : ""}
                  </span>
                  <span style={{ whiteSpace: "nowrap", color: JUDGE_COLOR[x.judgment] }}>
                    {x.amount_krw ? `${won(x.amount_krw)} · ` : ""}
                    {x.judgment}
                  </span>
                </div>
                {(x.judgment === "확인 필요" || x.mark) && u?.choices?.[x.section] && (
                  <select
                    aria-label={r.fixTitle}
                    value=""
                    onChange={(e) => e.target.value && fix(x.section, x.rank_no, e.target.value)}
                    style={{
                      fontSize: 13,
                      margin: "0 0 6px",
                      padding: "6px 8px",
                      borderRadius: 8,
                      border: "1px solid var(--line)",
                      background: "none",
                      color: "var(--blue)",
                    }}
                  >
                    <option value="">{r.fixTitle}</option>
                    {(u.choices?.[x.section] ?? []).map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            ))}
          </div>
          {lad.tenants.length > 0 && (
            <>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 8 }}>{r.tenants}</div>
              {lad.tenants.map((x, i) => (
                <div key={i} style={{ fontSize: 13, padding: "3px 0" }}>
                  {x.name ?? "임차인"} · 전입 {x.move_in ?? "-"}
                  {x.deposit_krw ? ` · ${won(x.deposit_krw)}` : ""} —{" "}
                  <b style={{ color: x.power ? "var(--red)" : "inherit" }}>{x.verdict}</b>
                </div>
              ))}
            </>
          )}
          {lad.payout && <PayoutBox p={lad.payout} />}
        </>
      )}
      {u?.status !== "processing" && (
        <>
          <label
            className="btn"
            style={{ display: "block", textAlign: "center", marginTop: 10, cursor: "pointer" }}
          >
            {u ? r.reupload : r.upload}
            <input
              type="file"
              accept="application/pdf"
              style={{ display: "none" }}
              onChange={(e) => {
                pick(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
          <p className="sub" style={{ fontSize: 12, marginBottom: 0 }}>
            {r.hint}
          </p>
        </>
      )}
      {err && <p style={{ color: "var(--red)", fontSize: 13 }}>{err}</p>}
      {u && (
        <p className="sub" style={{ fontSize: 12 }}>
          {r.keep(u.delete_after)}
        </p>
      )}
    </div>
  );
}

function HoldDocLink() {
  const openDoc = useContext(DocCtx);
  return (
    <button
      onClick={() => openDoc("status_report")}
      style={{
        border: 0,
        background: "none",
        color: "var(--blue)",
        fontSize: 13,
        padding: "8px 0",
        minHeight: 44,
      }}
    >
      {t.doc.openSr}
    </button>
  );
}

// 휴대폰: 실패 사례 11가지 중 걸린 것만, 나머지는 한 줄로 접음
function FailMobile({ rows }: { rows: NonNullable<ItemDetail["failure_table"]> }) {
  const [open, setOpen] = useState(false);
  const hit = rows.filter((r) => r.state === "걸림");
  const need = rows.filter((r) => r.state === "확인 필요").length;
  const none = rows.filter((r) => r.state === "신호 없음").length;
  return (
    <div className="m-block" style={{ marginTop: 10 }}>
      <div style={{ fontSize: 14, fontWeight: 700 }}>{t.failHead(rows.length, hit.length)}</div>
      {hit.map((r) => (
        <div key={r.code} style={{ fontSize: 14, padding: "6px 0", color: "var(--red)" }}>
          ◆ {r.title}
          <span className="sub" style={{ display: "block" }}>
            {r.why}
          </span>
        </div>
      ))}
      <button
        className="cond-row"
        style={{ background: "var(--bg)", marginTop: 6 }}
        onClick={() => setOpen(!open)}
      >
        <span style={{ fontSize: 14 }}>{t.failFold(none, need)}</span>
        <span className="sub">{open ? "▴" : "›"}</span>
      </button>
      {open &&
        rows
          .filter((r) => r.state !== "걸림")
          .map((r) => (
            <div key={r.code} className="line-row" style={{ fontSize: 13 }}>
              <span>{r.title}</span>
              <span
                style={{
                  color: r.state === "확인 필요" ? "var(--orange)" : "var(--faint)",
                  whiteSpace: "nowrap",
                }}
              >
                {r.state}
              </span>
            </div>
          ))}
      <div className="sub" style={{ fontSize: 12 }}>
        {t.failureTableNote}
      </div>
    </div>
  );
}

// 건축물대장(10/27): 사용승인·건물 모양·세대·승강기·주차, 이 층 용도(근생이면 빨강)
type Bldg = {
  built: string | null;
  old: boolean;
  shape: string | null;
  extra: string | null;
  unit: string | null;
  villa: "confirmed" | "mixed" | "clear" | null;
};
function BuildingRows({ g }: { g: Bldg }) {
  const c = t.bldg;
  const tone =
    g.villa === "confirmed" ? "var(--red)" : g.villa === "mixed" ? "var(--orange)" : undefined;
  return (
    <>
      {g.built && (
        <Row
          label={c.built}
          value={<span style={{ color: g.old ? "var(--orange)" : undefined }}>{g.built}</span>}
        />
      )}
      {g.shape && <Row label={c.shape} value={g.shape} />}
      {g.extra && <Row label="" value={g.extra} />}
      {g.unit && (
        <Row
          label={c.unit}
          value={
            <span style={{ color: tone }}>
              {g.unit}
              {g.villa === "confirmed"
                ? ` · ${c.villa}`
                : g.villa === "mixed"
                  ? ` · ${c.mixed}`
                  : ""}
            </span>
          }
        />
      )}
    </>
  );
}

function Body({ q, d }: { q: Question; d: ItemDetail }) {
  const b = q.body;
  if (q.key === "buy")
    return (
      <>
        <Row label="주소" value={b.address ?? "-"} />
        {b.area_m2 && (
          <Row
            label="면적"
            value={`${b.area_m2.toFixed(1)}㎡ (${Math.round(b.area_m2 / 3.3058)}평)`}
          />
        )}
        {b.is_share && <Row label="" value={<b style={{ color: "var(--red)" }}>{t.share}</b>} />}
        {b.building && <BuildingRows g={b.building} />}
        {b.redev && (
          <Row
            label={t.redev}
            value={[b.redev.name, b.redev.biz_type, b.redev.stage].filter(Boolean).join(" · ")}
          />
        )}
        {b.note && (
          <p className="sub" style={{ whiteSpace: "pre-wrap" }}>
            {b.note}
          </p>
        )}
      </>
    );
  if (q.key === "hold")
    return (
      <>
        {b.tenants.length === 0 && <p className="sub">{t.tenantsNone}</p>}
        {b.tenants.map((x: Record<string, string | number | null>, i: number) => (
          <div
            key={i}
            style={{ padding: "6px 0", fontSize: 14, borderBottom: "1px solid var(--line)" }}
          >
            <b>{x.name ?? "임차인"}</b> {x.part ?? ""}
            <div className="sub" style={{ margin: 0 }}>
              {[
                x.move_in && `${t.moveIn} ${x.move_in}`,
                x.fixed && `${t.fixed} ${x.fixed}`,
                x.claim && `${t.claim} ${x.claim}`,
                x.deposit_krw && `보증금 ${won(Number(x.deposit_krw))}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </div>
          </div>
        ))}
        <HoldDocLink />
        {d.failure_table ? (
          <FailMobile rows={d.failure_table} />
        ) : (
          d.failure_types.length > 0 && (
            <div className="sub" style={{ marginTop: 8 }}>
              {t.failureTypes}: {d.failure_types.map((x) => x.title).join(" · ")}
            </div>
          )
        )}
        {d.failure_table && (
          <div className="pc-only" style={{ marginTop: 12 }}>
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{t.failureTable}</div>
            <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
              <tbody>
                {d.failure_table.map((r) => (
                  <tr key={r.code} style={{ borderTop: "1px solid var(--line, #e5e5e5)" }}>
                    <td style={{ padding: "4px 6px", whiteSpace: "nowrap", opacity: 0.6 }}>
                      {r.code}
                    </td>
                    <td style={{ padding: "4px 6px" }}>{r.title}</td>
                    <td
                      style={{
                        padding: "4px 6px",
                        whiteSpace: "nowrap",
                        fontWeight: r.state === "신호 없음" ? 400 : 600,
                        color:
                          r.state === "걸림"
                            ? "var(--red, #d33)"
                            : r.state === "확인 필요"
                              ? "var(--orange, #d80)"
                              : undefined,
                        opacity: r.state === "신호 없음" ? 0.6 : 1,
                      }}
                    >
                      {r.state}
                    </td>
                    <td className="sub" style={{ padding: "4px 6px" }}>
                      {r.why}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="sub" style={{ marginTop: 4 }}>
              {t.failureTableNote}
            </div>
          </div>
        )}
        {b.signals
          .filter((s: { status: string }) => s.status !== "모름")
          .map((s: { rule_id: string; title: string; level: string }) => (
            <div
              key={s.rule_id}
              style={{
                fontSize: 14,
                padding: "6px 0",
                color: s.level === "fatal" ? "var(--red)" : "var(--amber)",
              }}
            >
              ◆ {s.title}
            </div>
          ))}
        <RegistryBox />
      </>
    );
  if (q.key === "worth")
    return b.range_krw ? (
      <>
        <Row
          label={t.rangeLabel}
          value={
            <b>
              {won(b.range_krw[0])} ~ {won(b.range_krw[1])}
            </b>
          }
        />
        <p className="sub">{t.sample(b.rate.n)}</p>
        {b.market && (
          <>
            <Row label={t.market(b.market.n)} value={<b>{won(b.market.price_krw)}</b>} />
            <div className="sub" style={{ margin: 0, fontSize: 12 }}>
              {t.recentTrades}{" "}
              {b.market.recent
                .slice(0, 3)
                .map(
                  (x: { date: string; floor: number | null; price_krw: number }) =>
                    `${x.date.slice(2, 7).replace("-", ".")} ${x.floor ?? "-"}층 ${won(x.price_krw)}`,
                )
                .join(" · ")}
            </div>
          </>
        )}
        {b.notes.map((n: string) => (
          <div key={n} style={{ fontSize: 14, color: "var(--amber)", padding: "2px 0" }}>
            ◆ {n}
          </div>
        ))}
      </>
    ) : null;
  if (q.key === "cost")
    return (
      <>
        <Row label={t.deposit} value={<b>{won(b.deposit_krw)}</b>} />
        <p style={{ fontSize: 14, margin: "8px 0 4px" }}>{b.schedule_line}</p>
        <div className="sub" style={{ margin: "8px 0 2px" }}>
          {t.deadlines}
        </div>
        {b.deadlines.map((x: { key: string; label: string; short: string }) => (
          <Row key={x.key} label={x.label} value={x.short} />
        ))}
        <CalcBox id={d.item_id} />
      </>
    );
  return <CheckBody b={b} />;
}

type CheckItem = {
  key: string;
  label: string;
  what: string;
  state: string;
  hint: string | null;
  evidence: { doc: string; fetched_at: string | null } | null;
  note?: string;
};

// 체크리스트의 등기부 줄을 내가 올린 등기부로 바꿈 (밤사이 분석은 손님 등기부를 모름)
const CHECK_ORDER: Record<string, number> = {
  "자료 충돌": 0,
  "전문가 확인 필요": 1,
  미확인: 2,
  "확인 완료": 3,
};
function withMyRegistry(list: CheckItem[], u: RegistryUpload | null | undefined): CheckItem[] {
  if (!u) return list;
  const r = t.reg;
  const out = list.map((x) => {
    if (x.key !== "registry") return x;
    if (u.status === "processing") return { ...x, state: "미확인", hint: r.checkReading };
    if (u.status !== "parsed" || !u.ladder) return x;
    const unsure = u.ladder.rows.filter(
      (w) => w.judgment === "확인 필요" || w.mark === "추정",
    ).length;
    const at = u.created_at ? new Date(u.created_at) : null;
    const pad = (n: number) => String(n).padStart(2, "0");
    return {
      ...x,
      state: "확인 완료",
      hint: null,
      evidence: {
        doc: r.checkDoc,
        fetched_at: at
          ? `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())} ${pad(at.getHours())}:${pad(at.getMinutes())}`
          : null,
      },
      note: unsure ? r.checkNote(unsure) : undefined,
    };
  });
  return out.sort((a, b) => (CHECK_ORDER[a.state] ?? 2) - (CHECK_ORDER[b.state] ?? 2));
}
type FlowStep = {
  key: string;
  label: string;
  date: string | null;
  estimated: boolean;
  done: boolean;
};
const STATE_CHIP: Record<string, string> = {
  "확인 완료": "green",
  미확인: "gray",
  "자료 충돌": "orange",
  "전문가 확인 필요": "orange",
};

// 올해는 「6/25」, 다른 해는 「25.6/25」
function flowDate(d: string): string {
  const md = `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;
  return d.slice(0, 4) === String(new Date().getFullYear()) ? md : `${d.slice(2, 4)}.${md}`;
}

// ITEM-06: 사건 흐름 막대 + 체크리스트(끝난 것은 접음) + 사건 문건
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CheckBody({ b }: { b: Record<string, any> }) {
  const [showDone, setShowDone] = useState(false);
  const reg = useContext(RegCtx);
  const openDoc = useContext(DocCtx);
  const list = withMyRegistry(b.checklist as CheckItem[], reg?.u);
  const todo = list.filter((x) => x.state !== "확인 완료");
  const done = list.filter((x) => x.state === "확인 완료");
  const flow = b.flow as FlowStep[];
  return (
    <>
      <div style={{ display: "flex", overflowX: "auto", gap: 0, padding: "4px 0 12px" }}>
        {flow.map((f, i) => (
          <div
            key={f.key}
            style={{ flex: "0 0 auto", minWidth: 64, textAlign: "center", fontSize: 11 }}
          >
            <div style={{ display: "flex", alignItems: "center" }}>
              <span style={{ flex: 1, height: 2, background: i ? "var(--line)" : "transparent" }} />
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 5,
                  background: f.done
                    ? "var(--green)"
                    : f.key === "now"
                      ? "var(--blue)"
                      : "var(--line)",
                }}
              />
              <span
                style={{
                  flex: 1,
                  height: 2,
                  background: i < flow.length - 1 ? "var(--line)" : "transparent",
                }}
              />
            </div>
            <div style={{ marginTop: 4, fontWeight: f.key === "now" ? 700 : 400 }}>{f.label}</div>
            <div className="sub" style={{ margin: 0, fontSize: 11 }}>
              {f.date ? flowDate(f.date) : "-"}
              {f.estimated && f.date ? ` ${t.flowGuess}` : ""}
            </div>
          </div>
        ))}
      </div>
      {todo.map((x) => (
        <div key={x.key} style={{ padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className={`chip ${STATE_CHIP[x.state] ?? "gray"}`}>{x.state}</span>
            <b style={{ fontSize: 14 }}>{x.label}</b>
          </div>
          <div className="sub" style={{ margin: "2px 0 0", fontSize: 12 }}>
            {x.what}
            {x.hint ? ` · ${x.hint}` : ""}
          </div>
        </div>
      ))}
      {done.length > 0 && (
        <button
          onClick={() => setShowDone(!showDone)}
          style={{
            border: 0,
            background: "none",
            color: "var(--muted)",
            fontSize: 13,
            padding: "10px 0",
            minHeight: 44,
          }}
        >
          ✓ {t.doneFold(done.length)} {showDone ? "⌃" : "›"}
        </button>
      )}
      {showDone &&
        done.map((x) => (
          <div key={x.key} style={{ fontSize: 13, padding: "4px 0" }}>
            <span style={{ color: "var(--green)" }}>✓</span> {x.label}
            <span className="sub" style={{ margin: 0 }}>
              {" "}
              · {x.evidence ? t.gotAt(x.evidence.doc, x.evidence.fetched_at) : ""}
              {x.note ? ` · ${x.note}` : ""}
            </span>
            {(x.key === "status_report" || x.key === "deliveries" || x.key === "spec_sheet") && (
              <button
                onClick={() => openDoc(x.key as DocKind)}
                style={{
                  border: 0,
                  background: "none",
                  color: "var(--blue)",
                  fontSize: 13,
                  padding: "0 0 0 6px",
                }}
              >
                {t.doc.open}
              </button>
            )}
          </div>
        ))}
      {b.events.length > 0 && (
        <div style={{ fontSize: 14, fontWeight: 600, marginTop: 10 }}>{t.events}</div>
      )}
      {b.events
        .slice(0, 6)
        .map((e: { date: string; category: string; after_deadline: boolean }, i: number) => (
          <div key={i} style={{ fontSize: 13, padding: "4px 0" }}>
            <span className="sub" style={{ margin: 0 }}>
              {e.date}
            </span>{" "}
            {e.category}
            {e.after_deadline && <b style={{ color: "var(--amber)" }}> · {t.afterDeadline}</b>}
          </div>
        ))}
    </>
  );
}

// 「무엇을 떠안나」 줄: 내가 올린 등기부가 있으면 그 결과로
function answerOf(q: Question, u: RegistryUpload | null | undefined): string {
  if (!u) return q.answer;
  if (q.key === "check" && Array.isArray(q.body?.checklist)) {
    const todo = withMyRegistry(q.body.checklist as CheckItem[], u).filter(
      (x) => x.state !== "확인 완료",
    );
    const first = todo[0];
    return first ? t.reg.checkLeft(todo.length, first.label) : t.reg.checkAll;
  }
  if (q.key !== "hold") return q.answer;
  if (u.status === "processing") return t.reg.summaryReading;
  if (u.status === "parsed" && u.ladder) return t.reg.summaryMine(u.ladder.line);
  return q.answer;
}

function WsLink({ id }: { id: string }) {
  const { ids } = useWatch();
  if (!ids.has(id)) return null;
  return (
    <Link href={`/watch/${encodeURIComponent(id)}`} className="chip gray" style={{ minHeight: 32 }}>
      {copy.ws.open} ›
    </Link>
  );
}

// PC 물건 상세(PC-ITEM): 위 요약 띠 + 목차 14 · 본문 62 · 행동 칸 24. 다섯 질문을 모두 펼칩니다.
function CompareAdd({ id }: { id: string }) {
  const { session } = useSession();
  const [msg, setMsg] = useState("");
  if (!session) return null;
  return (
    <button
      className="pc-act"
      onClick={() =>
        meApi
          .addCompare(session.access_token, id)
          .then(() => setMsg(copy.compare.added))
          .catch(() => setMsg(copy.compare.full(5)))
      }
    >
      {msg || copy.compare.add}
    </button>
  );
}

function ItemPc({ d, reg }: { d: ItemDetail; reg: MyReg }) {
  const [copied, setCopied] = useState(false);
  const id = encodeURIComponent(d.item_id);
  const urgent = d.d_day != null && d.d_day <= 7;
  const stats: [string, React.ReactNode][] = [
    [
      t.pc.sale,
      <>
        <b style={{ color: urgent ? "var(--red)" : "var(--amber)" }}>{dday(d.d_day)}</b>{" "}
        {d.sale_date ?? "-"}
      </>,
    ],
    [t.pc.appraisal, won(d.appraisal_krw)],
    [
      t.pc.min,
      <>
        {won(d.min_price_krw)} <span className="sub">{d.min_rate}%</span>
      </>,
    ],
    [t.pc.failed, d.failed_count ? copy.card.failed(d.failed_count) : t.pc.none],
    [
      t.nextRound,
      d.next_round.min_price_krw
        ? `${won(d.next_round.min_price_krw)}${d.next_round.verified ? "" : ` ${t.nextRoundGuess}`}`
        : "-",
    ],
    [t.pc.deposit, won(d.deposit_krw)],
  ];
  return (
    <main className="page">
      <PageHeader
        title={`${d.place} ${d.building ?? d.usage ?? ""}`}
        sub={
          <span style={{ display: "inline-flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <span>
              {d.court} {d.case_no}
              {d.dept_name ? ` · ${d.dept_name}` : ""}
              {d.sale_place ? ` · ${d.sale_place}` : ""}
            </span>
            <button
              className="chip gray"
              style={{ border: 0, minHeight: 28 }}
              onClick={() => {
                navigator.clipboard?.writeText(d.case_no).then(() => setCopied(true));
              }}
            >
              {copied ? t.pc.copied : t.pc.copy}
            </button>
          </span>
        }
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <WsLink id={d.item_id} />
            <HeartButton id={d.item_id} />
          </div>
        }
      />
      {d.fatal && <div className="fatal">{d.fatal}</div>}
      <section className="section">
        <div className="band-grid">
          {stats.map(([k, v]) => (
            <div key={k}>
              <div className="sub" style={{ margin: 0 }}>
                {k}
              </div>
              <div style={{ fontSize: 17, fontWeight: 700, marginTop: 2 }}>{v}</div>
            </div>
          ))}
        </div>
        <p style={{ fontSize: 18, fontWeight: 600, lineHeight: 1.5, margin: "14px 0 0" }}>
          {d.verdict}
        </p>
        {d.tags.length > 0 && (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
            {d.tags.map((x) => (
              <span key={x.label} className={`chip ${x.ok ? "green" : "gray"}`}>
                {x.label}
              </span>
            ))}
          </div>
        )}
      </section>
      <div className="pc-grid g-14-62-24">
        <nav className="section pc-sticky toc" aria-label={t.pc.toc}>
          {d.questions.map((q) => (
            <a key={q.key} href={`#q-${q.key}`}>
              <span className="toc-dot" style={{ background: DOT[q.tone] }} />
              {q.title}
            </a>
          ))}
          <a href="#q-rounds">
            <span className="toc-dot" style={{ background: "var(--faint)" }} />
            {t.rounds}
          </a>
        </nav>
        <div>
          {d.questions.map((q) => (
            <section key={q.key} id={`q-${q.key}`} className="section q-sec">
              <div className="sub" style={{ margin: 0 }}>
                {q.title}
              </div>
              <h2 style={{ display: "flex", gap: 8, alignItems: "baseline", margin: "4px 0 12px" }}>
                <span className="toc-dot" style={{ background: DOT[q.tone] }} />
                {answerOf(q, reg.u)}
              </h2>
              <Body q={q} d={d} />
            </section>
          ))}
          <section id="q-rounds" className="section q-sec">
            <h2>{t.rounds}</h2>
            <table className="pro-table" style={{ marginTop: 8 }}>
              <thead>
                <tr>
                  <th>{t.pc.date}</th>
                  <th>{t.pc.min}</th>
                  <th>{t.pc.result}</th>
                </tr>
              </thead>
              <tbody>
                {d.rounds.map((r) => (
                  <tr key={r.sale_date}>
                    <td>{r.sale_date}</td>
                    <td>{won(r.min_price_krw)}</td>
                    <td>{r.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <p className="sub" style={{ fontSize: 12 }}>
            {t.footer(d.computed_at ? d.computed_at.slice(0, 10) : "-")}
          </p>
        </div>
        <aside className="section pc-sticky pc-actions">
          <div style={{ fontSize: 15, fontWeight: 700 }}>{t.pc.actions}</div>
          <Link
            href={`/item/${id}/calc`}
            className="btn primary"
            style={{ height: 46, fontSize: 15 }}
          >
            {t.bidTry}
          </Link>
          <Link href={`/item/${id}/bid-sheet`} className="pc-act">
            {copy.bidSheet.title}
          </Link>
          <Link href={`/item/${id}/bid-day`} className="pc-act">
            {copy.bidDay.title}
          </Link>
          <CompareAdd id={d.item_id} />
          <Link href="/pro/market" className="pc-act">
            {t.pc.market}
          </Link>
          <button className="pc-act" onClick={() => window.print()}>
            {t.pc.print}
          </button>
          <div className="sub" style={{ fontSize: 12 }}>
            {t.pc.basis(d.computed_at ? d.computed_at.slice(0, 16).replace("T", " ") : "-")}
          </div>
        </aside>
      </div>
    </main>
  );
}

export default function Item() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<ItemDetail | null | undefined>(undefined);
  const [open, setOpen] = useState<string | null>(null);
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
        rememberItem(
          x.item_id,
          `${x.court} ${x.case_no} · ${x.place} ${x.building ?? x.usage ?? ""}`,
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
      <main className="page" aria-busy="true">
        <div className="topbar" />
        {[120, 260].map((h) => (
          <section key={h} className="section" style={{ height: h, opacity: 0.5 }} />
        ))}
      </main>
    );
  if (d === null)
    return (
      <main className="page">
        <p className="sub" style={{ padding: 24 }}>
          {t.notFound}
        </p>
      </main>
    );
  const urgent = d.d_day != null && d.d_day <= 7;
  if (pc)
    return (
      <RegCtx.Provider value={reg}>
        <DocCtx.Provider value={setDoc}>
          <ItemPc d={d} reg={reg} />
          {doc && <DocSheet id={d.item_id} kind={doc} onClose={() => setDoc(null)} />}
        </DocCtx.Provider>
      </RegCtx.Provider>
    );
  return (
    <RegCtx.Provider value={reg}>
      <DocCtx.Provider value={setDoc}>
        <main className="page">
          <PageHeader
            title=""
            back="history"
            right={
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <WsLink id={d.item_id} />
                <HeartButton id={d.item_id} />
              </div>
            }
          />
          {d.fatal && <div className="fatal">{d.fatal}</div>}
          {d.d_day != null && d.d_day <= 1 && d.d_day >= 0 && (
            <Link
              href={`/item/${encodeURIComponent(d.item_id)}/bid-day`}
              className="chip orange"
              style={{ minHeight: 36, marginTop: 8, display: "inline-flex" }}
            >
              {copy.bidDay.title} ›
            </Link>
          )}
          <section className="section">
            <div className="sub">
              <b style={{ color: urgent ? "var(--red)" : "var(--amber)" }}>{dday(d.d_day)}</b> ·{" "}
              {d.sale_date} · {d.court} {d.case_no}
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, marginTop: 4 }}>
              {d.place} {d.building ?? d.usage}
            </div>
            <div style={{ fontSize: 30, fontWeight: 700, marginTop: 6 }}>
              {won(d.min_price_krw)}{" "}
              <span style={{ fontSize: 14, fontWeight: 500, color: "var(--muted)" }}>
                {copy.card.ofAppraisal} {d.min_rate}%
                {d.failed_count ? ` · ${copy.card.failed(d.failed_count)}` : ""}
              </span>
            </div>
            <p style={{ fontSize: 16, lineHeight: 1.5, margin: "12px 0 0" }}>{d.verdict}</p>
          </section>

          <section className="section" style={{ paddingTop: 0, paddingBottom: 0 }}>
            {d.questions.map((q) => (
              <div key={q.key} style={{ borderBottom: "1px solid var(--line)" }}>
                <button
                  onClick={() => setOpen(open === q.key ? null : q.key)}
                  style={{
                    width: "100%",
                    border: 0,
                    background: "none",
                    textAlign: "left",
                    padding: "14px 0",
                    minHeight: 44,
                    display: "flex",
                    gap: 10,
                    alignItems: "flex-start",
                    color: "inherit",
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      background: DOT[q.tone],
                      marginTop: 7,
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ flexGrow: 1 }}>
                    <span className="sub" style={{ display: "block", margin: 0, fontSize: 13 }}>
                      {q.title}
                    </span>
                    <span style={{ fontSize: 15, fontWeight: 600 }}>{answerOf(q, reg.u)}</span>
                  </span>
                  <span aria-hidden="true" style={{ color: "var(--faint)" }}>
                    {open === q.key ? "⌃" : "›"}
                  </span>
                </button>
                {open === q.key && (
                  <div style={{ padding: "0 0 14px 18px" }}>
                    <Body q={q} d={d} />
                  </div>
                )}
              </div>
            ))}
          </section>

          <section className="section">
            {d.next_round.min_price_krw && (
              <Row
                label={t.nextRound}
                value={
                  <b>
                    {won(d.next_round.min_price_krw)}
                    {d.next_round.verified ? "" : ` ${t.nextRoundGuess}`}
                  </b>
                }
              />
            )}
            {d.rounds.length > 0 && (
              <div style={{ fontSize: 14, fontWeight: 600, margin: "10px 0 2px" }}>{t.rounds}</div>
            )}
            {d.rounds.map((r) => (
              <Row
                key={r.sale_date}
                label={r.sale_date}
                value={`${won(r.min_price_krw)} · ${r.result}`}
              />
            ))}
          </section>
          <p className="sub" style={{ padding: "0 18px 24px", fontSize: 12 }}>
            {t.footer(d.computed_at ? d.computed_at.slice(0, 10) : "-")}
          </p>
          {doc && <DocSheet id={d.item_id} kind={doc} onClose={() => setDoc(null)} />}
        </main>
      </DocCtx.Provider>
    </RegCtx.Provider>
  );
}
