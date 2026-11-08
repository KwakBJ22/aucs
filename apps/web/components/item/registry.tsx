"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { meApi, uploadRegistry, type RegistryUpload } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { parseTime, won } from "@/lib/format";
import { useIsPc } from "@/lib/use-pc";
import { t, JUDGE_COLOR, DocCtx } from "@/components/item/shared";

// 등기부 올리기 + 권리 사다리(ITEM-03). 올린 사람만 봄.
// 내가 올린 등기부: 상세 화면 전체가 같이 씀(「무엇을 떠안나」 요약 줄도 이걸로 바뀜)
export type MyReg = {
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

export const RegCtx = createContext<MyReg | null>(null);

export function useMyRegistry(id: string): MyReg {
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
            setStartedAt(
              (v) => v ?? (x.created_at ? parseTime(x.created_at).getTime() : Date.now()),
            );
            // 그림 등기부(ocr_wait)는 글자 읽기를 기다리는 중이라 1분마다만 확인(11/3)
            timer = setTimeout(load, x.method === "ocr_wait" ? 60_000 : 3000);
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
export const EXPECT_SEC = 40;

export function ReadingBar({ sending, startedAt }: { sending: boolean; startedAt: number | null }) {
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
      <div className="d-flex jc-between fs-md">
        <b>{r.reading}</b>
        <span className="sub m-0">{r.left(Math.round(EXPECT_SEC - sec))}</span>
      </div>
      <div className="r-4 bg-line mt-8" style={{ height: 8 }}>
        <div
          className="r-4 bg-blue"
          style={{ width: `${pct}%`, height: 8, transition: "width .5s linear" }}
        />
      </div>
      <div className="d-flex gap-12 fs-xs mt-6">
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

export function PayoutBox({ p }: { p: NonNullable<RegistryUpload["ladder"]>["payout"] & object }) {
  const [open, setOpen] = useState(false);
  const r = t.reg;
  return (
    <div className="mt-8">
      <button
        onClick={() => setOpen(!open)}
        className="b-0 bg-none py-8 px-0 mh-44 fs-md fw-6 c-inherit"
      >
        {r.payTitle(won(p.price_krw))} {open ? "⌃" : "›"}
      </button>
      {open && (
        <>
          {p.rows.map((x, i) => (
            <div
              key={i}
              className="d-flex jc-between gap-8 fs-sm py-2 px-0"
              style={{ color: x.paid_krw ? "inherit" : "var(--muted)" }}
            >
              <span>
                {i + 1}. {x.name}
              </span>
              <span className="nowrap">
                {won(x.paid_krw)}
                {x.claim_krw && x.claim_krw > x.paid_krw ? ` / ${won(x.claim_krw)}` : ""}
              </span>
            </div>
          ))}
          {p.surplus_krw > 0 && (
            <div className="d-flex jc-between fs-sm py-2 px-0">
              <span>{r.payLeft}</span>
              <span>{won(p.surplus_krw)}</span>
            </div>
          )}
          {p.unknown.length > 0 && (
            <p className="fs-xs c-amber mt-6 mb-0 mx-0">{r.payUnknown(p.unknown.join(", "))}</p>
          )}
          <p className="sub fs-xs mt-4 mb-0 mx-0">{r.payNote}</p>
        </>
      )}
    </div>
  );
}

export function RegistryBox() {
  const r = t.reg;
  const reg = useContext(RegCtx);
  const pc = useIsPc();
  const [ladOpen, setLadOpen] = useState(false);
  if (!reg || !reg.ready) return null;
  const { token, u, err, pick, fix, accept, sending, startedAt } = reg;
  const addr = u?.status === "parsed" ? u.address : undefined;
  const blocked =
    !!addr && !addr.ok && (addr.result === "different" || addr.result === "unit_differs");
  if (!token) return <p className="sub mt-10">{r.needLogin}</p>;
  const lad = u?.ladder;
  return (
    <div className="mt-12 pt-10">
      {u?.status === "processing" &&
        (u.method === "ocr_wait" ? (
          <p className="note blue">{t.reg.ocrWait}</p>
        ) : (
          <ReadingBar sending={sending} startedAt={startedAt} />
        ))}
      {blocked && addr && (
        <div className="bg-orange-soft r-16 p-14">
          <b className="c-amber fs-base">
            {addr.result === "unit_differs" && addr.registry_unit && addr.item_unit
              ? r.addrUnit(addr.registry_unit, addr.item_unit)
              : r.addrDiff}
          </b>
          <div className="fs-sm mt-8 lh-15">
            <div>
              <span className="sub m-0">{r.addrReg}</span> {addr.registry}
            </div>
            <div>
              <span className="sub m-0">{r.addrItem}</span> {addr.item}
            </div>
          </div>
          <button onClick={accept} className="b-0 bg-none c-muted fs-sm pt-10 pb-0 px-0 mh-44">
            {r.addrStill} ›
          </button>
        </div>
      )}
      {lad && addr?.result === "unknown" && (
        <p className="fs-sm c-amber mt-0 mb-6 mx-0">{r.addrUnknown}</p>
      )}
      {u?.status === "failed" && <p className="c-amber fs-md">{r.failed}</p>}
      {lad && (
        <>
          <div className="fs-base fw-7">{lad.line}</div>
          {lad.spec_check && (
            <div
              className="fs-xs mt-4"
              style={{
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
            <button className="cond-row bg-bg" onClick={() => setLadOpen(!ladOpen)}>
              <span>
                <b>
                  {r.foldTitle(
                    lad.rows.length,
                    lad.rows.filter((x) => x.judgment !== "소멸").length,
                  )}
                </b>
                {lad.base && (
                  <span className="sub d-block">
                    {r.foldBase(lad.base.name, lad.base.date ?? "")}
                  </span>
                )}
              </span>
              <span className="sub">{ladOpen ? "▴" : "›"}</span>
            </button>
          )}
          <div className="mt-6" style={{ display: pc || ladOpen ? "block" : "none" }}>
            {lad.rows.map((x) => (
              <div key={`${x.section}${x.rank_no}`}>
                {x.is_base && lad.base && (
                  <div className="fs-xs c-blue py-6 px-0">
                    {r.baseLine(lad.base.name, lad.base.date ?? "")}
                  </div>
                )}
                <div
                  className="d-flex jc-between gap-8 fs-sm py-4 px-0"
                  style={{ color: x.judgment === "소멸" ? "var(--muted)" : "inherit" }}
                >
                  <span>
                    {x.date ?? "-"} · {x.name}
                    {x.mark ? <span className="c-muted"> ({x.mark})</span> : null}
                    {x.holder ? ` · ${x.holder}` : ""}
                  </span>
                  <span className="nowrap" style={{ color: JUDGE_COLOR[x.judgment] }}>
                    {x.amount_krw ? `${won(x.amount_krw)} · ` : ""}
                    {x.judgment}
                  </span>
                </div>
                {(x.judgment === "확인 필요" || x.mark) && u?.choices?.[x.section] && (
                  <select
                    aria-label={r.fixTitle}
                    value=""
                    onChange={(e) => e.target.value && fix(x.section, x.rank_no, e.target.value)}
                    className="fs-sm mt-0 mb-6 mx-0 py-6 px-8 r-14 b-0 bg-panel c-blue"
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
              <div className="fs-md fw-6 mt-8">{r.tenants}</div>
              {lad.tenants.map((x, i) => (
                <div key={i} className="fs-sm py-2 px-0">
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
          <label className="btn secondary mt-10 cur-pointer" style={{ height: 48 }}>
            {u ? r.reupload : r.upload}
            <input
              type="file"
              accept="application/pdf"
              className="d-none"
              onChange={(e) => {
                pick(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
          <p className="sub fs-xs mb-0">{r.hint}</p>
        </>
      )}
      {err && <p className="c-red fs-sm">{err}</p>}
      {u && <p className="sub fs-xs">{r.keep(u.delete_after)}</p>}
    </div>
  );
}

export function HoldDocLink() {
  const openDoc = useContext(DocCtx);
  return (
    <button
      onClick={() => openDoc("status_report")}
      className="b-0 bg-none c-blue fs-sm py-8 px-0 mh-44"
    >
      {t.doc.openSr}
    </button>
  );
}
