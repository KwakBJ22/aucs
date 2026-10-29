"use client";

import { useContext, useState } from "react";
import { Termed } from "@/components/term";
import type { DocKind, Question } from "@/lib/api/items";
import type { RegistryUpload } from "@/lib/api/me";
import { RegCtx } from "@/components/item/registry";
import { t, DocCtx } from "@/components/item/shared";

export type CheckItem = {
  key: string;
  label: string;
  what: string;
  state: string;
  hint: string | null;
  evidence: { doc: string; fetched_at: string | null } | null;
  note?: string;
};

// 체크리스트의 등기부 줄을 내가 올린 등기부로 바꿈 (밤사이 분석은 손님 등기부를 모름)
export const CHECK_ORDER: Record<string, number> = {
  "자료 충돌": 0,
  "전문가 확인 필요": 1,
  미확인: 2,
  "확인 완료": 3,
};

export function withMyRegistry(
  list: CheckItem[],
  u: RegistryUpload | null | undefined,
): CheckItem[] {
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

export type FlowStep = {
  key: string;
  label: string;
  date: string | null;
  estimated: boolean;
  done: boolean;
};

export const STATE_CHIP: Record<string, string> = {
  "확인 완료": "green",
  미확인: "gray",
  "자료 충돌": "orange",
  "전문가 확인 필요": "orange",
};

// 올해는 「6/25」, 다른 해는 「25.6/25」
export function flowDate(d: string): string {
  const md = `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;
  return d.slice(0, 4) === String(new Date().getFullYear()) ? md : `${d.slice(2, 4)}.${md}`;
}

// ITEM-06: 사건 흐름 막대 + 체크리스트(끝난 것은 접음) + 사건 문건
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function CheckBody({ b }: { b: Record<string, any> }) {
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
        <div key={x.key} style={{ padding: "8px 0" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className={`chip ${STATE_CHIP[x.state] ?? "gray"}`}>{x.state}</span>
            <b style={{ fontSize: 14 }}>
              <Termed text={x.label} />
            </b>
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
export function answerOf(q: Question, u: RegistryUpload | null | undefined): string {
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
