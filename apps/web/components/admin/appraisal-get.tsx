"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { DDay } from "@/components/dday";
import { COURT_CASE_PAGE } from "@/components/item/appraisal";
import { t as itemT } from "@/components/item/shared";
import { adminApi, type AppraisalSaved, type AppraisalTargets } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { parseTime } from "@/lib/format";
import { errText, useAdmin, when } from "./ctx";

const t = copy.admin.getAppraisal;
const dDay = (iso: string | null) =>
  iso ? Math.round((parseTime(iso).getTime() - new Date().setHours(0, 0, 0, 0)) / 864e5) : null;

// 법원 창: 이름(court)으로 찾아 — 비어 있으면(처음) 그때만 법원 주소로, 이미 법원 화면이면(다른 주소라 읽으면 오류) 앞으로만
function openCourt() {
  const w = window.open("", "court");
  if (!w) {
    window.open(COURT_CASE_PAGE, "court");
    return;
  }
  try {
    if (w.location.href === "about:blank") w.location.href = COURT_CASE_PAGE;
  } catch {
    // 이미 법원 사이트가 열려 있음 — 다시 불러오지 않음
  }
  w.focus();
}

// 감정평가서 받기(11/14 대표님): 손님 화면처럼 법원에서 받되, 올리는 일은 PC 의 받은 폴더가 알아서.
// 11/25 대표님: 위에서 시군구로 고르고, 법원 사이트는 맨 위 링크로 한 번만 열어 둠 — 줄마다는 「복사」만(새 창 없음)
export function AppraisalGet() {
  const { token, say } = useAdmin();
  const [d, setD] = useState<AppraisalTargets | null>(null);
  const [areas, setAreas] = useState<AppraisalTargets["areas"]>([]);
  const [area, setArea] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [soon, setSoon] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<Record<string, string>>({});
  const load = useCallback(
    (offset: number, sg: string) =>
      adminApi
        .appraisalTargets(token, offset, sg, soon)
        .then((x) => {
          if (!offset && !sg && x.areas.length) setAreas(x.areas);
          setD((v) => (offset && v ? { ...x, rows: [...v.rows, ...x.rows] } : x));
        })
        .catch((e) => say(errText(e))),
    [token, say, soon],
  );
  useEffect(() => {
    void load(0, area);
  }, [load, area]);
  const send = (caseId: string, f: File | undefined) => {
    if (!f) return;
    setBusy(caseId);
    adminApi
      .uploadAppraisal(token, caseId, f)
      .then((s: AppraisalSaved) => {
        const msg = !s.ok
          ? t.wrong(s.why)
          : s.already
            ? t.already
            : t.saved(s.firm, s.pages) + (s.scanned ? t.scanned : "");
        setDone((x) => ({ ...x, [caseId]: msg }));
      })
      .catch((e) => say(errText(e)))
      .finally(() => setBusy(null));
  };
  if (!d) return null;
  const all = areas.reduce((n, a) => n + a.n, 0);
  const copyNo = (caseNo: string) => {
    const num = caseNo.split("타경")[1] ?? caseNo;
    navigator.clipboard?.writeText(num).then(
      () => setCopied(caseNo),
      () => setCopied(null),
    );
  };
  return (
    <section className="section">
      <h2>{t.title(d.total)}</h2>
      <p className="sub">{t.order(d.home, d.station)}</p>
      {d.last && (
        <p className="sub adm-msg">
          {t.last}: {when(d.last.started_at)} · {d.last.message ?? ""}
        </p>
      )}
      <div className="adm-line mt-8">
        <select
          className="adm-input"
          aria-label={t.areaLabel}
          value={area}
          onChange={(e) => setArea(e.target.value)}
        >
          <option value="">{t.allAreas(all || d.total)}</option>
          {areas.map((a) => (
            <option key={a.area} value={a.area}>
              {t.area(a.area, a.n)}
            </option>
          ))}
        </select>
        {/* 11/26 대표님: 처음에만 열고, 이미 열려 있으면 다시 불러오지 않고 그 창으로만(적어 둔 검색이 남게) */}
        <button type="button" className="btn soft sm" onClick={openCourt}>
          {t.openCourt}
        </button>
        <button
          type="button"
          className={`btn sm ${soon ? "primary" : "soft"}`}
          onClick={() => setSoon((v) => !v)}
        >
          {soon ? t.soonOn : t.soon}
        </button>
      </div>
      <p className="sub fs-sm mt-6">{soon ? t.soonHint : t.openHint}</p>
      {d.rows.map((r) => {
        const [year = "", num = r.case_no] = r.case_no.split("타경");
        return (
          <div key={r.case_id} className="adm-card">
            <Link
              prefetch={false}
              href={`/item/${encodeURIComponent(r.item_id)}`}
              target="_blank"
              className="link fw-6"
            >
              {r.place}
            </Link>
            <div className="sub mt-2">
              <DDay d={dDay(r.sale_date)} /> · {r.court} {r.case_no}
              {r.home && <span className="chip blue ml-6">{t.home}</span>}
              {r.station && <span className="chip green ml-6">{t.station}</span>}
            </div>
            <div className="adm-line mt-8">
              <button type="button" className="btn soft sm" onClick={() => copyNo(r.case_no)}>
                {t.copy}
              </button>
              <label className="btn soft sm">
                {busy === r.case_id ? t.busy : t.pick}
                <input
                  type="file"
                  accept="application/pdf"
                  hidden
                  disabled={busy === r.case_id}
                  onChange={(e) => send(r.case_id, e.target.files?.[0])}
                />
              </label>
              {copied === r.case_no && (
                <p className="sub fs-sm w-full m-0">{itemT.appraisal.copied(r.court, year, num)}</p>
              )}
            </div>
            {done[r.case_id] && <p className="sub fs-sm m-0">{done[r.case_id]}</p>}
          </div>
        );
      })}
      {d.rows.length < d.total && (
        <button className="adm-btn mt-8" onClick={() => load(d.next, area)}>
          {t.more}
        </button>
      )}
    </section>
  );
}
