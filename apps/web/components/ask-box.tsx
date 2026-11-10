"use client";

import { useEffect, useState } from "react";
import { meApi, type MyInquiry } from "@/lib/api/me";
import { copy } from "@/lib/copy.ko";

const t = copy.ask;

// 문의하기(11/2): 보내면 관리자 「회원」에 쌓이고, 답은 알림함으로.
// 처음 목록은 「내 정보」 묶음(/me/more)에서 받아 옴(11/3) — 보낸 뒤에만 다시 부름.
export function AskBox({ token, initial }: { token: string; initial: MyInquiry[] }) {
  const [rows, setRows] = useState<MyInquiry[]>(initial);
  const [body, setBody] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => {
    meApi
      .inquiries(token)
      .then(setRows)
      .catch(() => {});
  };
  useEffect(() => setRows(initial), [initial]);
  return (
    <section className="section" id="ask">
      <h2>{t.title}</h2>
      <textarea
        className="memo-box"
        rows={3}
        maxLength={2000}
        placeholder={t.ph}
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <button
        className="btn soft w-full mt-8"
        disabled={body.trim().length < 2}
        onClick={() =>
          meApi
            .ask(token, body.trim())
            .then(() => {
              setBody("");
              setMsg(t.sent);
              load();
            })
            .catch(() => setMsg(t.fail))
        }
      >
        {t.send}
      </button>
      {msg && <p className="sub mt-8">{msg}</p>}
      {rows.map((r) => (
        <div key={r.inquiry_id} className="adm-card">
          <div className="adm-msg">{r.body}</div>
          <div className={r.answer ? "note blue adm-msg" : "sub"}>{r.answer ?? t.waiting}</div>
        </div>
      ))}
    </section>
  );
}
