"use client";

import { Delayed, SkRows } from "@/components/skeleton";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { adminApi, type Review } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { Confirm, errText, useAdmin, when } from "./ctx";

const t = copy.admin;
type Tab = "reports" | "fields" | "signals";

// 3 자료 검수: 제보 / 읽은 칸 / 위험 신호 — 매각기일 가까운 순
export function ReviewView() {
  const { token, say, can } = useAdmin();
  const [d, setD] = useState<Review | null>(null);
  const [tab, setTab] = useState<Tab>("reports");
  const [edit, setEdit] = useState<Record<number, string>>({});
  const [hidden, setHidden] = useState<{ item_id: string; address: string | null }[]>([]);
  const load = useCallback(() => {
    adminApi
      .screen(token, "review")
      .then((x) => {
        setD(x.review);
        setHidden(x.hidden);
      })
      .catch((e) => say(errText(e)));
  }, [token, say]);
  useEffect(load, [load]);
  if (!d)
    return (
      <Delayed>
        <SkRows n={8} />
      </Delayed>
    );
  const op = can("operator");
  const run = (p: Promise<unknown>) =>
    p
      .then(() => {
        say(t.done);
        load();
      })
      .catch((e) => say(errText(e)));
  const item = (id: string) => (
    <Link href={`/item/${encodeURIComponent(id)}`} target="_blank">
      {id}
    </Link>
  );
  return (
    <>
      <div className="adm-tabs">
        {(["reports", "fields", "signals"] as const).map((k) => (
          <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>
            {t.reviewTabs[k]} {d.total[k].toLocaleString("ko-KR")}
          </button>
        ))}
      </div>
      <section className="section">
        {d[tab].length === 0 && <p className="sub">{t.none}</p>}
        {tab === "reports" &&
          d.reports.map((r) => (
            <div key={r.report_id} className="adm-card">
              <div className="sub">
                {item(r.item_id)} · {r.sale_date ?? ""} · {when(r.created_at)}
              </div>
              <div>
                <b>{r.section}</b> {r.note}
              </div>
              {op && (
                <div className="adm-line">
                  {(["fixed", "rejected"] as const).map((st) => (
                    <button
                      key={st}
                      className="adm-btn"
                      onClick={() => run(adminApi.closeReport(token, r.report_id, st))}
                    >
                      {t.reportAction[st]}
                    </button>
                  ))}
                  <Confirm
                    label={t.hide}
                    ask={t.hideAsk}
                    onYes={() => run(adminApi.hide(token, r.item_id, true, r.note))}
                  />
                </div>
              )}
            </div>
          ))}
        {tab === "fields" &&
          d.fields.map((f) => (
            <div key={f.field_id} className="adm-card">
              <div className="sub">
                {f.case_id} · {f.doc_kind} · {f.sale_date ?? ""}
              </div>
              <div>
                <b>{f.field}</b> {JSON.stringify(f.value)}
              </div>
              {f.raw_text && <div className="sub adm-msg">{f.raw_text}</div>}
              {op && (
                <div className="adm-line">
                  <button
                    className="adm-btn"
                    onClick={() => run(adminApi.checkField(token, f.field_id))}
                  >
                    {t.fieldOk}
                  </button>
                  <input
                    className="adm-input"
                    placeholder={t.fieldNew}
                    value={edit[f.field_id] ?? ""}
                    onChange={(e) => setEdit({ ...edit, [f.field_id]: e.target.value })}
                  />
                  <button
                    className="adm-btn"
                    disabled={!edit[f.field_id]}
                    onClick={() => run(adminApi.checkField(token, f.field_id, edit[f.field_id]))}
                  >
                    {t.fieldFix}
                  </button>
                </div>
              )}
            </div>
          ))}
        {tab === "signals" &&
          d.signals.map((s) => (
            <div key={s.signal_id} className="adm-card">
              <div className="sub">
                {item(s.item_id)} · {s.sale_date} · {s.address ?? ""}
              </div>
              <div>
                <span
                  className={`chip ${s.level === "fatal" || s.level === "high" ? "orange" : "gray"}`}
                >
                  {t.level[s.level] ?? s.level}
                </span>{" "}
                {s.title}
              </div>
              {op && (
                <div className="adm-line">
                  <button
                    className="adm-btn"
                    onClick={() => run(adminApi.decideSignal(token, s.item_id, s.rule_id, "확정"))}
                  >
                    {t.sigYes}
                  </button>
                  <button
                    className="adm-btn"
                    onClick={() => run(adminApi.decideSignal(token, s.item_id, s.rule_id, "없음"))}
                  >
                    {t.sigNo}
                  </button>
                  <button
                    className="adm-btn"
                    onClick={() =>
                      adminApi
                        .requestJob(token, `analyze_item:${s.item_id}`)
                        .then(() => say(t.requestOk))
                        .catch((e) => say(errText(e)))
                    }
                  >
                    {t.reanalyze}
                  </button>
                  <Confirm
                    label={t.hide}
                    ask={t.hideAsk}
                    onYes={() => run(adminApi.hide(token, s.item_id, true, s.title))}
                  />
                </div>
              )}
            </div>
          ))}
      </section>
      {hidden.length > 0 && (
        <section className="section">
          <h2>{t.hiddenTitle}</h2>
          {hidden.map((h) => (
            <div key={h.item_id} className="adm-row">
              <span>
                {h.item_id} <span className="sub">{h.address ?? ""}</span>
              </span>
              {op && (
                <button
                  className="adm-btn"
                  onClick={() => run(adminApi.hide(token, h.item_id, false))}
                >
                  {t.show}
                </button>
              )}
            </div>
          ))}
        </section>
      )}
    </>
  );
}
