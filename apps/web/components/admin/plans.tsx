"use client";

import { useCallback, useEffect, useState } from "react";
import { Delayed, SkRows } from "@/components/skeleton";
import { adminApi, type PlansScreen } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { Confirm, errText, useAdmin, when } from "./ctx";

const t = copy.admin;
const m = copy.admin.money;
// 가격 칸: 이용권 · 기간 (전문가는 지금 숨겨 둔 상품이지만 값은 함께 둠)
const CELLS = [
  ["personal", "month"],
  ["personal", "year"],
  ["one", "one"],
  ["pro", "month"],
  ["pro", "year"],
] as const;

// 새 가격은 기본으로 내일부터(오늘 결제한 손님 값이 하루 안에 바뀌지 않게)
function tomorrow(): string {
  const d = new Date(Date.now() + 9 * 3600e3 + 864e5); // 한국 날짜
  return d.toISOString().slice(0, 10);
}

// 이용권·포인트(11/12): 가격 바꾸기 · 지금 쓰는 이용권 · 결제 · 포인트 흐름 · 많이 받은 회원 · 최근 내역
export function PlansView() {
  const { token, say, can } = useAdmin();
  const [d, setD] = useState<PlansScreen | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [from, setFrom] = useState(tomorrow);
  const [why, setWhy] = useState("");
  const load = useCallback(() => {
    adminApi
      .screen(token, "plans")
      .then(setD)
      .catch((e) => say(errText(e)));
  }, [token, say]);
  useEffect(load, [load]);

  if (!d)
    return (
      <Delayed>
        <SkRows n={8} />
      </Delayed>
    );

  const val = (p: string, k: string) => d.prices[p]?.[k as "month"] ?? 0;
  const next = () => {
    const out: Record<string, Record<string, number>> = {};
    for (const [p, k] of CELLS) {
      const raw = draft[`${p}.${k}`];
      (out[p] ??= {})[k] = raw ? Number(raw) : val(p, k);
    }
    return out;
  };
  const changed = Object.values(draft).some((x) => x !== "");

  return (
    <>
      <section className="section">
        <h2>{m.price}</h2>
        <p className="sub">{m.priceNote}</p>
        <div className="adm-prices">
          {CELLS.map(([p, k]) => (
            <label key={`${p}.${k}`} className="adm-price">
              <span className="sub">
                {m.planName[p]} · {m.period[k]}
              </span>
              {can("owner") ? (
                <input
                  className="adm-input"
                  inputMode="numeric"
                  placeholder={val(p, k).toLocaleString("ko-KR")}
                  value={draft[`${p}.${k}`] ?? ""}
                  onChange={(e) =>
                    setDraft({ ...draft, [`${p}.${k}`]: e.target.value.replace(/\D/g, "") })
                  }
                />
              ) : (
                <b>{val(p, k).toLocaleString("ko-KR")}원</b>
              )}
            </label>
          ))}
        </div>
        {can("owner") && changed && (
          <div className="adm-line">
            <input
              type="date"
              className="adm-input"
              title={m.from}
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
            <input
              className="adm-input f-1"
              placeholder={m.why}
              value={why}
              onChange={(e) => setWhy(e.target.value)}
            />
            {why.trim().length >= 2 && (
              <Confirm
                label={m.change}
                ask={m.changeAsk}
                onYes={() =>
                  adminApi
                    .newRule(token, "plans", from, next(), why.trim())
                    .then(() => {
                      say(m.changed);
                      setDraft({});
                      setWhy("");
                      load();
                    })
                    .catch((e) => say(errText(e)))
                }
              />
            )}
          </div>
        )}
        {d.price_rows.map((r) => (
          <p key={r.valid_from} className="sub fs-sm mt-4">
            {m.hist(r.valid_from, !!r.reviewed_at)} · {r.basis}
          </p>
        ))}
      </section>

      <section className="section">
        <h2>{m.using}</h2>
        {Object.keys(d.plans).length === 0 && <p className="sub">{t.none}</p>}
        {Object.entries(d.plans).map(([p, n]) => (
          <div key={p} className="adm-row">
            <span>{m.planName[p] ?? p}</span>
            <span className="sub">{m.usingLine(n.paid ?? 0, n.grant ?? 0)}</span>
          </div>
        ))}
      </section>

      <section className="section">
        <h2>{m.pays}</h2>
        <p className="sub">{m.monthLine(Number(d.month.krw), Number(d.month.n))}</p>
        {d.payments.length === 0 && <p className="sub">{m.payNone}</p>}
        {d.payments.map((x) => (
          <div key={x.payment_id} className="adm-row">
            <span className="ellipsis">
              {when(x.paid_at)} · {x.email} · {m.planName[x.plan] ?? x.plan} {m.period[x.period]}
            </span>
            <span className="sub">{m.payLine(x.amount_krw, x.points_used, x.refunded_krw)}</span>
          </div>
        ))}
      </section>

      <section className="section">
        <h2>{m.points}</h2>
        <p>{m.pointsLine(d.points.earned, d.points.spent, d.points.left, d.points.people)}</p>
        <h3 className="mt-16">{m.uploads}</h3>
        {d.uploads.length === 0 && <p className="sub">{t.none}</p>}
        {d.uploads.map((x) => (
          <div key={`${x.kind}.${x.status}`} className="adm-row">
            <span>
              {m.kind[x.kind] ?? x.kind} · {m.upStatus[x.status] ?? x.status}
            </span>
            <span className="sub">{m.topLine(Number(x.pts), Number(x.n))}</span>
          </div>
        ))}
        <h3 className="mt-16">{m.top}</h3>
        {d.top.length === 0 && <p className="sub">{t.none}</p>}
        {d.top.map((x) => (
          <div key={x.user_id} className="adm-row">
            <span className="ellipsis">{x.email}</span>
            <span className="sub">{m.topLine(Number(x.earned), Number(x.n))}</span>
          </div>
        ))}
        <h3 className="mt-16">{m.ledger}</h3>
        {d.ledger.length === 0 && <p className="sub">{t.none}</p>}
        {d.ledger.map((x) => (
          <div key={x.entry_id} className="adm-row">
            <span className="ellipsis">
              {when(x.created_at)} · {x.email} · {m.reason[x.reason] ?? x.reason}
              {x.item_id ? ` · ${x.item_id}` : ""}
            </span>
            <b className={x.delta > 0 ? "c-green" : "c-red"}>
              {x.delta > 0 ? "+" : ""}
              {x.delta.toLocaleString("ko-KR")}P
            </b>
          </div>
        ))}
      </section>
    </>
  );
}
