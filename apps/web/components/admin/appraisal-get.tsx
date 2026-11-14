"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { DDay } from "@/components/dday";
import { OriginalLink } from "@/components/item/appraisal";
import { adminApi, type AppraisalTargets } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { parseTime } from "@/lib/format";
import { errText, useAdmin, when } from "./ctx";

const t = copy.admin.getAppraisal;
const dDay = (iso: string | null) =>
  iso ? Math.round((parseTime(iso).getTime() - new Date().setHours(0, 0, 0, 0)) / 864e5) : null;

// 감정평가서 받기(11/14 대표님): 손님 화면처럼 법원에서 받되, 올리는 일은 PC 의 받은 폴더가 알아서
export function AppraisalGet() {
  const { token, say } = useAdmin();
  const [d, setD] = useState<AppraisalTargets | null>(null);
  const load = useCallback(
    (offset: number) =>
      adminApi
        .appraisalTargets(token, offset)
        .then((x) => setD((v) => (offset && v ? { ...x, rows: [...v.rows, ...x.rows] } : x)))
        .catch((e) => say(errText(e))),
    [token, say],
  );
  useEffect(() => {
    void load(0);
  }, [load]);
  if (!d) return null;
  return (
    <section className="section">
      <h2>{t.title(d.total)}</h2>
      <p className="sub">{t.how}</p>
      <p className="sub">{t.order(d.home, d.station)}</p>
      {d.last && (
        <p className="sub adm-msg">
          {t.last}: {when(d.last.started_at)} · {d.last.message ?? ""}
        </p>
      )}
      {d.rows.map((r) => (
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
            <OriginalLink court={r.court} caseNo={r.case_no} compact />
          </div>
        </div>
      ))}
      {d.rows.length < d.total && (
        <button className="adm-btn mt-8" onClick={() => load(d.next)}>
          {t.more}
        </button>
      )}
    </section>
  );
}
