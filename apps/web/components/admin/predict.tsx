"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Delayed, SkRows } from "@/components/skeleton";
import { adminApi, type PredictFactor, type PredictScreen } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { errText, useAdmin } from "./ctx";

const t = copy.admin.predict;
const SHADOW_MIN_N = 50; // 「그림자가 나음」 칩은 현행 · 그림자 모두 이 건수 이상일 때만

function Factor({ f, months }: { f: PredictFactor; months: string[] }) {
  const isFail = f.key.startsWith("fail:");
  const tag = f.wrong_way
    ? { cls: "orange", text: t.wrong }
    : !f.enough
      ? { cls: "gray", text: t.few }
      : f.steady
        ? { cls: "green", text: t.pass }
        : { cls: "gray", text: t.unsteady };
  return (
    <div className="adm-card">
      <div className="adm-line mt-0">
        <b>{f.name}</b>
        {!isFail && <b>{t.effect(f.effect)}</b>}
        {!isFail && <span className={`chip ${tag.cls}`}>{tag.text}</span>}
      </div>
      <span className="sub">{t.line(f.ratio, f.n, f.n_without)}</span>
      {!isFail && (
        <span className="sub">
          {months.map((m) => t.month(m, f.by_month[m] ?? null)).join(" · ")}
        </span>
      )}
      {f.wrong_way && (
        <>
          <span className="sub">{t.wrongNote}</span>
          {f.examples.map((x) => (
            <Link key={x.item_id} href={`/item/${encodeURIComponent(x.item_id)}`} target="_blank">
              {x.sale_date} · {x.ratio}% · {x.address ?? x.item_id}
            </Link>
          ))}
        </>
      )}
    </div>
  );
}

// 낙찰가 예측(11/21 대표님 — 핵심 경쟁력): 성적표 · 쌓인 기록 · 요인표. 셈은 API 가 낙찰 순간 기록으로(1시간 기억)
export function PredictView() {
  const { token, say } = useAdmin();
  const [d, setD] = useState<PredictScreen | null>(null);
  const [u, setU] = useState<"apt" | "villa">("apt");
  const [kind, setKind] = useState("전체");
  useEffect(() => {
    adminApi
      .screen(token, "predict")
      .then(setD)
      .catch((e) => say(errText(e)));
  }, [token, say]);

  if (!d)
    return (
      <Delayed>
        <SkRows n={8} />
      </Delayed>
    );
  const list = d.factors.filter((f) => f.u === u);
  const kinds = [...new Set(d.shadow_market.rows.map((r) => r.kind))].filter((k) => k !== "전체");
  const shadowRows = d.shadow_market.rows.filter((r) => r.kind === kind);
  return (
    <>
      <section className="section">
        <h2>{t.score}</h2>
        {d.score.length === 0 && <p className="sub">{t.none}</p>}
        {d.score.map((s) => (
          <div key={s.month} className="adm-row">
            <span>{s.month}</span>
            <span>{t.scoreRow(s.n, s.inside, s.below, s.above)}</span>
          </div>
        ))}
        <p className="sub">{t.scoreNote}</p>
      </section>
      {d.score_split.length > 0 && (
        <section className="section">
          <h2>{t.split}</h2>
          {d.score_split.map((s) => (
            <div key={`${s.kind}${s.g}`} className="adm-row">
              <span>
                {s.kind} · {t.splitFail(s.g)}
              </span>
              <span className="sub">{s.few ? t.splitFew(s.n) : t.splitRow(s)}</span>
            </div>
          ))}
          <p className="sub">{t.splitNote(15)}</p>
        </section>
      )}
      <section className="section">
        <div className="adm-row">
          <h2>{t.shadow}</h2>
          <div className="adm-tabs">
            {["전체", ...kinds].map((k) => (
              <button key={k} className={kind === k ? "on" : ""} onClick={() => setKind(k)}>
                {k === "전체" ? t.all : k}
              </button>
            ))}
          </div>
        </div>
        {shadowRows.length === 0 && <p className="sub">{t.none}</p>}
        {shadowRows.map((r) => {
          const better =
            r.shadow.n >= SHADOW_MIN_N &&
            r.current.n >= SHADOW_MIN_N &&
            (r.shadow.inside ?? 0) > (r.current.inside ?? 0) &&
            (r.shadow.mid_err ?? 0) < (r.current.mid_err ?? 0);
          return (
            <div key={r.month} className="adm-card">
              <div className="adm-line mt-0">
                <b>{r.month}</b>
                {better && <span className="chip green">{t.shadowBetter}</span>}
                <span className="sub">{t.shadowExcluded(r.excluded)}</span>
              </div>
              <span className="sub">
                {t.shadowCols[0]} {t.shadowCell(r.current)}
              </span>
              <span className="sub">
                {t.shadowCols[1]} {t.shadowCell(r.shadow)}
              </span>
            </div>
          );
        })}
        <p className="sub">{t.shadowNote(d.shadow_market.pool_min, d.shadow_market.pool_days)}</p>
      </section>
      <section className="section">
        <div className="adm-row">
          <h2>{t.factors}</h2>
          <div className="adm-tabs">
            {(["apt", "villa"] as const).map((k) => (
              <button key={k} className={u === k ? "on" : ""} onClick={() => setU(k)}>
                {t.kinds[k]}
              </button>
            ))}
          </div>
        </div>
        <p className="sub">{t.sample(d.sample[u] ?? 0)}</p>
        <p className="sub">{t.rule(d.rule.min_side, d.rule.months)}</p>
        {list.length === 0 && <p className="sub">{t.none}</p>}
        {list.map((f) => (
          <Factor key={f.key} f={f} months={d.months} />
        ))}
      </section>
      <section className="section">
        <h2>{t.kept}</h2>
        {d.kept.map((k) => (
          <div key={k.month} className="adm-row">
            <span>{k.month}</span>
            <span className="sub">{t.keptRow(k.sold, k.failed, k.sold_market)}</span>
          </div>
        ))}
      </section>
    </>
  );
}
