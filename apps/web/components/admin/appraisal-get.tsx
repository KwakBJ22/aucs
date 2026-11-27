"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { DDay } from "@/components/dday";
import { COURT_CASE_PAGE } from "@/components/item/appraisal";
import { adminApi, type AppraisalTargets } from "@/lib/api/admin";
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
  const load = useCallback(
    (offset: number, sg: string) =>
      adminApi
        .appraisalTargets(token, offset, sg, soon)
        .then((x) => {
          // 시군구 건수는 우선 목록 · 전체 목록마다 그 기준으로 새로(11/27)
          if (!offset) setAreas(x.areas);
          setD((v) => (offset && v ? { ...x, rows: [...v.rows, ...x.rows] } : x));
        })
        .catch((e) => say(errText(e))),
    [token, say, soon],
  );
  useEffect(() => {
    void load(0, area);
  }, [load, area]);
  // 복사 뒤 2초 동안만 단추 글자를 「복사함」으로
  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => setCopied(null), 2000);
    return () => window.clearTimeout(id);
  }, [copied]);
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
          {/* 고른 시군구가 이 목록에 없으면(0건) 고르기는 그대로 두고 그 칸만 0건으로 보임 */}
          {area && !areas.some((a) => a.area === area) && (
            <option value={area}>{t.area(area, 0)}</option>
          )}
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
      {d.rows.map((r) => (
        <div key={r.case_id} className="adm-card adm-item">
          <Link
            prefetch={false}
            href={`/item/${encodeURIComponent(r.item_id)}`}
            target="_blank"
            className="link fw-6 adm-item-addr"
          >
            {r.place}
          </Link>
          <div className="sub adm-item-info">
            <DDay d={dDay(r.sale_date)} /> · {r.court} {r.case_no}
            {r.home && <span className="chip blue ml-6">{t.home}</span>}
            {r.station && <span className="chip green ml-6">{t.station}</span>}
          </div>
          <div className="adm-item-btns">
            <button type="button" className="btn soft sm" onClick={() => copyNo(r.case_no)}>
              {copied === r.case_no ? t.copied : t.copy}
            </button>
          </div>
        </div>
      ))}
      {d.rows.length < d.total && (
        <button className="adm-btn mt-8" onClick={() => load(d.next, area)}>
          {t.more}
        </button>
      )}
    </section>
  );
}
