"use client";

import { Delayed, SkLines } from "@/components/skeleton";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  adminApi,
  type Inquiry,
  type RefundReq,
  type UserDetail,
  type UserRow,
} from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { Confirm, errText, useAdmin, when } from "./ctx";

const t = copy.admin;

// 4 회원: 문의(답 안 한 것) + 회원 목록 → 상세(이용권 주기·이용 제한·메일 보기)
export function MembersView() {
  const { token, say, can } = useAdmin();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<UserRow[]>([]);
  const [inq, setInq] = useState<Inquiry[]>([]);
  const [ans, setAns] = useState<Record<number, string>>({});
  const [open, setOpen] = useState<string | null>(null);
  const [refunds, setRefunds] = useState<RefundReq[]>([]);
  const [rAns, setRAns] = useState<Record<number, string>>({});
  const load = useCallback(() => {
    adminApi
      .screen(token, "members")
      .then((x) => {
        setRows(x.users);
        setInq(x.inquiries);
        setRefunds(x.refunds);
      })
      .catch((e) => say(errText(e)));
  }, [token, say]);
  useEffect(load, [load]);
  // 찾기 칸을 고칠 때는 회원 목록만 다시
  const lastQ = useRef(q);
  useEffect(() => {
    if (lastQ.current === q) return; // 처음 목록은 위에서 받음(개발 모드에서 두 번 돌아도 안전)
    lastQ.current = q;
    const h = window.setTimeout(() => {
      adminApi
        .users(token, q)
        .then(setRows)
        .catch((e) => say(errText(e)));
    }, 300);
    return () => window.clearTimeout(h);
  }, [token, q, say]);
  return (
    <>
      {refunds.length > 0 && (
        <section className="section">
          <h2>
            {t.refunds} {refunds.length}
          </h2>
          {refunds.map((r) => (
            <div key={r.request_id} className="adm-card">
              <div className="sub">
                {r.email} · {when(r.created_at)} · {copy.billing.planName[r.plan] ?? r.plan}{" "}
                {copy.billing.periodName[r.period] ?? r.period}
              </div>
              <div>{t.refundLine(r.amount_krw, r.estimate_krw)}</div>
              {r.reason && <div className="sub adm-msg">{r.reason}</div>}
              {can("owner") && (
                <div className="adm-line">
                  <input
                    className="adm-input"
                    placeholder={t.refundAnswer}
                    value={rAns[r.request_id] ?? ""}
                    onChange={(e) => setRAns({ ...rAns, [r.request_id]: e.target.value })}
                  />
                  {(rAns[r.request_id] ?? "").trim().length >= 2 && (
                    <>
                      <Confirm
                        label={t.refundOk}
                        ask={t.refundOkAsk}
                        onYes={() =>
                          adminApi
                            .decideRefund(token, r.request_id, true, rAns[r.request_id] ?? "")
                            .then(() => {
                              say(t.done);
                              load();
                            })
                            .catch((e) => say(errText(e)))
                        }
                      />
                      <button
                        className="adm-btn"
                        onClick={() =>
                          adminApi
                            .decideRefund(token, r.request_id, false, rAns[r.request_id] ?? "")
                            .then(() => {
                              say(t.done);
                              load();
                            })
                            .catch((e) => say(errText(e)))
                        }
                      >
                        {t.refundNo}
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </section>
      )}
      <section className="section">
        <h2>
          {t.inquiries} {inq.length}
        </h2>
        {inq.length === 0 && <p className="sub">{t.none}</p>}
        {inq.map((x) => (
          <div key={x.inquiry_id} className="adm-card">
            <div className="sub">
              {x.email} · {when(x.created_at)}
            </div>
            <div className="adm-msg">{x.body}</div>
            {can("operator") && (
              <div className="adm-line">
                <textarea
                  className="adm-input"
                  rows={2}
                  value={ans[x.inquiry_id] ?? ""}
                  onChange={(e) => setAns({ ...ans, [x.inquiry_id]: e.target.value })}
                  placeholder={t.answerPh}
                />
                <button
                  className="adm-btn primary"
                  disabled={(ans[x.inquiry_id] ?? "").trim().length < 2}
                  onClick={() =>
                    adminApi
                      .answer(token, x.inquiry_id, ans[x.inquiry_id] ?? "")
                      .then(() => {
                        say(t.answered);
                        load();
                      })
                      .catch((e) => say(errText(e)))
                  }
                >
                  {t.answerGo}
                </button>
              </div>
            )}
          </div>
        ))}
      </section>
      <section className="section">
        <h2>
          {t.members} {rows.length}
        </h2>
        <input
          className="adm-input w-full"
          placeholder={t.memberSearch}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {rows.map((u) => (
          <div key={u.user_id}>
            <button
              className="adm-row adm-click"
              onClick={() => setOpen(open === u.user_id ? null : u.user_id)}
            >
              <span>
                {u.email}
                {u.admin_role && <span className="chip blue ml-6">{t.roleName[u.admin_role]}</span>}
                {u.limited && <span className="chip orange ml-6">{t.limited}</span>}
              </span>
              <span className="sub">{u.plan ?? t.free}</span>
              <span className="sub">{when(u.last_sign_in_at)}</span>
            </button>
            {open === u.user_id && <Detail id={u.user_id} reload={load} />}
          </div>
        ))}
      </section>
    </>
  );
}

function Detail({ id, reload }: { id: string; reload: () => void }) {
  const { token, say, can } = useAdmin();
  const [u, setU] = useState<UserDetail | null>(null);
  const [email, setEmail] = useState("");
  const [plan, setPlan] = useState("pro");
  const [days, setDays] = useState(30);
  const [reason, setReason] = useState("");
  const [limitWhy, setLimitWhy] = useState("");
  const load = useCallback(() => {
    adminApi
      .user(token, id)
      .then(setU)
      .catch((e) => say(errText(e)));
  }, [token, id, say]);
  useEffect(load, [load]);
  if (!u)
    return (
      <Delayed>
        <SkLines n={6} />
      </Delayed>
    );
  const done = () => {
    say(t.done);
    load();
    reload();
  };
  return (
    <div className="adm-detail">
      <p className="sub">
        {t.joined} {when(u.created_at)} · {t.purposeName[u.purpose ?? ""] ?? "-"} ·{" "}
        {(u.interest_regions ?? []).join(", ") || "-"}
      </p>
      <p className="sub">{t.counts(u)}</p>
      {can("owner") && (
        <p>
          {email || (
            <button
              className="adm-btn"
              onClick={() =>
                adminApi
                  .revealEmail(token, id)
                  .then((r) => setEmail(r.email))
                  .catch((e) => say(errText(e)))
              }
            >
              {t.showEmail}
            </button>
          )}
        </p>
      )}
      {u.grants.map((g) => (
        <p key={g.created_at} className="sub">
          {t.grantLine(g.plan, g.until_date, g.reason)}
        </p>
      ))}
      {can("operator") && (
        <div className="adm-line">
          <select className="adm-input" value={plan} onChange={(e) => setPlan(e.target.value)}>
            <option value="basic">basic</option>
            <option value="pro">pro</option>
          </select>
          <select
            className="adm-input"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            {[7, 30, 90, 365].map((n) => (
              <option key={n} value={n}>
                {n}일
              </option>
            ))}
          </select>
          <input
            className="adm-input"
            placeholder={t.reason}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button
            className="adm-btn"
            disabled={reason.trim().length < 2}
            onClick={() =>
              adminApi
                .grant(token, id, plan, days, reason)
                .then(done)
                .catch((e) => say(errText(e)))
            }
          >
            {t.grantGo}
          </button>
        </div>
      )}
      {can("owner") &&
        (u.limit_reason ? (
          <div className="adm-line">
            <span className="chip orange">
              {t.limited} · {u.limit_reason}
            </span>
            <button
              className="adm-btn"
              onClick={() =>
                adminApi
                  .limit(token, id, null)
                  .then(done)
                  .catch((e) => say(errText(e)))
              }
            >
              {t.unlimit}
            </button>
          </div>
        ) : (
          <div className="adm-line">
            <input
              className="adm-input"
              placeholder={t.limitWhy}
              value={limitWhy}
              onChange={(e) => setLimitWhy(e.target.value)}
            />
            {limitWhy.trim().length >= 2 && (
              <Confirm
                danger
                label={t.limitGo}
                ask={t.limitAsk}
                onYes={() =>
                  adminApi
                    .limit(token, id, limitWhy)
                    .then(done)
                    .catch((e) => say(errText(e)))
                }
              />
            )}
          </div>
        ))}
    </div>
  );
}
