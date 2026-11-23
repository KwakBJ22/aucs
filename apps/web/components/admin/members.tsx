"use client";

import { Delayed, SkLines } from "@/components/skeleton";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  adminApi,
  type Inquiry,
  type MemberFilter,
  type MemberSort,
  type MemberSummary,
  type RefundReq,
  type UserDetail,
  type UserRow,
} from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { parseTime } from "@/lib/format";
import { Confirm, errText, useAdmin, when } from "./ctx";

const t = copy.admin;
const m = copy.admin.money;

const FILTERS: MemberFilter[] = ["all", "paid", "limited", "admin", "away"];
const day = (s: string | null | undefined) =>
  s
    ? parseTime(s).toLocaleDateString("ko-KR", {
        year: "2-digit",
        month: "numeric",
        day: "numeric",
      })
    : "-";

// 4 회원: 문의(답 안 한 것) + 회원 목록(숫자 · 거르기 · 정렬 · 더 보기) → 상세(등록 정보 · 접속 · 결제 · 활동 · 이용권 주기 · 이용 제한 · 메일 보기)
export function MembersView() {
  const { token, say, can } = useAdmin();
  const [q, setQ] = useState("");
  const [f, setF] = useState<MemberFilter>("all");
  const [sort, setSort] = useState<MemberSort>("joined");
  const [rows, setRows] = useState<UserRow[]>([]);
  const [more, setMore] = useState(false);
  const [sum, setSum] = useState<MemberSummary | null>(null);
  const [inq, setInq] = useState<Inquiry[]>([]);
  const [ans, setAns] = useState<Record<number, string>>({});
  const [open, setOpen] = useState<string | null>(null);
  const [refunds, setRefunds] = useState<RefundReq[]>([]);
  const [rAns, setRAns] = useState<Record<number, string>>({});
  const load = useCallback(() => {
    adminApi
      .screen(token, "members")
      .then((x) => {
        setRows(x.users.rows);
        setMore(x.users.more);
        setSum(x.summary);
        setInq(x.inquiries);
        setRefunds(x.refunds);
      })
      .catch((e) => say(errText(e)));
  }, [token, say]);
  useEffect(load, [load]);
  // 찾기 · 거르기 · 정렬을 바꿀 때는 회원 목록만 다시(찾기 칸은 멈춘 뒤 한 번)
  const page = useCallback(
    (offset: number) =>
      adminApi
        .users(token, q, f, sort, offset)
        .then((x) => {
          setRows((r) => (offset ? [...r, ...x.rows] : x.rows));
          setMore(x.more);
        })
        .catch((e) => say(errText(e))),
    [token, q, f, sort, say],
  );
  const last = useRef(`${q}|${f}|${sort}`);
  useEffect(() => {
    const key = `${q}|${f}|${sort}`;
    if (last.current === key) return; // 처음 목록은 위에서 받음(개발 모드에서 두 번 돌아도 안전)
    const typed = last.current.split("|")[0] !== q;
    last.current = key;
    const h = window.setTimeout(() => void page(0), typed ? 300 : 0);
    return () => window.clearTimeout(h);
  }, [q, f, sort, page]);
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
          {t.members} {sum?.total ?? rows.length}
        </h2>
        {sum && <p className="sub">{t.memberSum(sum)}</p>}
        <div className="adm-line">
          <div className="adm-tabs f-wrap">
            {FILTERS.map((k) => (
              <button key={k} className={f === k ? "on" : ""} onClick={() => setF(k)}>
                {t.memberFilter[k]} {k === "all" ? (sum?.total ?? "") : (sum?.[k] ?? "")}
              </button>
            ))}
          </div>
          <select
            className="adm-input"
            value={sort}
            onChange={(e) => setSort(e.target.value as MemberSort)}
          >
            {(["joined", "login"] as const).map((k) => (
              <option key={k} value={k}>
                {t.sortName[k]}
              </option>
            ))}
          </select>
        </div>
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
                <span className="sub ml-6">{t.provider[u.provider] ?? u.provider}</span>
                {u.admin_role && <span className="chip blue ml-6">{t.roleName[u.admin_role]}</span>}
                {u.limited && <span className="chip orange ml-6">{t.limited}</span>}
                {!u.confirmed && <span className="chip orange ml-6">{t.unconfirmed}</span>}
              </span>
              <span className="sub">
                {u.paid_plan && u.paid_until
                  ? t.paidUntil(u.paid_plan, u.paid_until)
                  : (u.plan ?? t.free)}
              </span>
              <span className="sub">{t.rowDates(day(u.created_at), when(u.last_sign_in_at))}</span>
            </button>
            {open === u.user_id && <Detail id={u.user_id} reload={load} />}
          </div>
        ))}
        {more && (
          <button className="adm-btn w-full" onClick={() => void page(rows.length)}>
            {t.more}
          </button>
        )}
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
  const [pts, setPts] = useState("");
  const [ptsWhy, setPtsWhy] = useState("");
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
      <b>{t.info}</b>
      <p className="sub">
        {u.nickname ?? "-"} · {t.provider[u.provider] ?? u.provider}
        {!u.email_confirmed_at && ` · ${t.unconfirmed}`} · {t.joined} {when(u.created_at)}
      </p>
      <p className="sub">
        {t.purposeName[u.purpose ?? ""] ?? "-"} · {(u.interest_regions ?? []).join(", ") || "-"} ·{" "}
        {t.cash(u.cash_krw)} · {t.homes(u.homes, u.first_time)} · {t.profileAt} {when(u.profile_at)}
      </p>
      <b>{t.access}</b>
      <p className="sub">
        {t.lastSignIn} {when(u.last_sign_in_at)} · {t.lastSeen} {when(u.last_seen)} ·{" "}
        {t.loginN(u.login_n)} · {t.push(u.push_n)}
      </p>
      <b>{t.activity}</b>
      <p className="sub">
        {t.counts(u)} · {t.viewN(u.view_n)} · {t.academyN(u.academy_n)} · {m.memberPoints(u.points)}
      </p>
      <b>{t.pays}</b>
      <p className="sub">{t.card(u.card)}</p>
      {u.payments.length === 0 && <p className="sub">{t.none}</p>}
      {u.payments.map((p) => (
        <p key={p.payment_id} className="sub">
          {day(p.paid_at)} · {t.payLine(p)}
          {p.auto_renew && ` · ${t.autoRenew(p.renew_fails)}`}
        </p>
      ))}
      {u.ledger.length > 0 && (
        <details>
          <summary className="sub">
            {t.ledger} {u.ledger.length}
          </summary>
          {u.ledger.map((l, i) => (
            <p key={i} className="sub">
              {when(l.created_at)} · {l.delta > 0 ? "+" : ""}
              {l.delta.toLocaleString()}P · {l.reason}
            </p>
          ))}
        </details>
      )}
      {u.inquiries.length > 0 && (
        <details>
          <summary className="sub">
            {t.inquiries} {u.inquiries.length}
          </summary>
          {u.inquiries.map((x) => (
            <div key={x.inquiry_id} className="adm-card">
              <span className="sub">{when(x.created_at)}</span>
              <span className="adm-msg">{x.body}</span>
              {x.answer && <span className="sub adm-msg">↳ {x.answer}</span>}
            </div>
          ))}
        </details>
      )}
      {u.events.length > 0 && (
        <details>
          <summary className="sub">
            {t.recent} {u.events.length}
          </summary>
          {u.events.map((e, i) => (
            <p key={i} className="sub">
              {when(e.at)} · {t.eventName[e.kind] ?? e.kind}
              {e.path ? ` · ${decodeURIComponent(e.path)}` : ""}
            </p>
          ))}
        </details>
      )}
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
      {can("owner") && (
        <div className="adm-line">
          <input
            className="adm-input adm-short"
            inputMode="numeric"
            placeholder={m.adjustHint}
            title={m.adjust}
            value={pts}
            onChange={(e) => setPts(e.target.value.replace(/[^\d-]/g, ""))}
          />
          <input
            className="adm-input"
            placeholder={m.adjustWhy}
            value={ptsWhy}
            onChange={(e) => setPtsWhy(e.target.value)}
          />
          {Number(pts) !== 0 && ptsWhy.trim().length >= 2 && (
            <Confirm
              label={m.adjustGo}
              ask={m.adjustAsk(Number(pts))}
              onYes={() =>
                adminApi
                  .points(token, id, Number(pts), ptsWhy.trim())
                  .then((r) => {
                    say(m.adjusted(r.balance));
                    setPts("");
                    setPtsWhy("");
                    load();
                  })
                  .catch((e) => say(errText(e)))
              }
            />
          )}
        </div>
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
