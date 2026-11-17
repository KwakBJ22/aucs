"use client";

import Link from "next/link";
import { useState } from "react";
import { apiBaseUrl } from "@/lib/api/client";
import { copy } from "@/lib/copy.ko";

const t = copy.guestAsk;

// 로그인 없이 남기는 문의(11/17): 경매 정보 속 개인정보 삭제 · 가림 요청(채무자 · 소유자 · 임차인은 회원이 아님) ·
// 로그인 문제 · 탈퇴 뒤 · 권리 침해 · 제휴. 답은 알림함이 아니라 남긴 연락처로.
export function GuestAsk() {
  const [kind, setKind] = useState("privacy");
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [caseNo, setCaseNo] = useState("");
  const [body, setBody] = useState("");
  const [agree, setAgree] = useState(false);
  const [msg, setMsg] = useState("");
  const ok = name.trim() && contact.trim().length >= 5 && body.trim().length >= 2 && agree;
  const send = () =>
    fetch(`${apiBaseUrl}/guest/inquiries`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, name, contact, case_no: caseNo, body }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        setBody("");
        setMsg(t.sent);
      })
      .catch(() => setMsg(t.fail));
  return (
    <section className="section" id="ask">
      <h2>{copy.ask.title}</h2>
      <p className="sub">{t.sub}</p>
      <Link href="/login" className="btn soft mt-8">
        {copy.help.login}
      </Link>
      <h3 className="mt-16">{t.title}</h3>
      <select className="memo-box" value={kind} onChange={(e) => setKind(e.target.value)}>
        {Object.entries(t.kinds).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </select>
      <input
        className="memo-box mt-8"
        maxLength={30}
        placeholder={t.name}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className="memo-box mt-8"
        maxLength={60}
        placeholder={t.contact}
        value={contact}
        onChange={(e) => setContact(e.target.value)}
      />
      {kind === "privacy" && (
        <input
          className="memo-box mt-8"
          maxLength={30}
          placeholder={t.caseNo}
          value={caseNo}
          onChange={(e) => setCaseNo(e.target.value)}
        />
      )}
      <textarea
        className="memo-box mt-8"
        rows={4}
        maxLength={1500}
        placeholder={kind === "privacy" ? t.bodyPrivacy : t.body}
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <label className="d-flex gap-8 ai-center fs-sm mt-8">
        <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
        {t.agree}
      </label>
      <button className="btn soft w-full mt-8" disabled={!ok} onClick={send}>
        {copy.ask.send}
      </button>
      {msg && <p className="sub mt-8">{msg}</p>}
    </section>
  );
}
