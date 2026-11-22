"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { useState } from "react";
import { sendLoginLink, signInWithKakao, signOut, userLabel, useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.loginPage;

export default function Login() {
  const { session } = useSession();
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [byMail, setByMail] = useState(false);

  return (
    <main className="page narrow">
      <PageHeader title="" back="/home" />
      {/* 11/22 디자인: 가운데 카드 · 위에 옥스경매 글자 · 카카오(노랑) · 이메일(회색, 누르면 칸) · 약관 한 줄 */}
      <section className="section login-card">
        <div className="login-brand">{copy.appName}</div>
        <h1 className="login-title">{session ? t.title : t.head}</h1>
        {session ? (
          <>
            <p className="sub fs-base">{t.loggedIn(userLabel(session))}</p>
            <button className="btn secondary" onClick={() => void signOut()}>
              {t.logout}
            </button>
          </>
        ) : (
          <>
            <p className="login-body">{t.body}</p>
            <button
              className="btn kakao mt-16"
              onClick={async () => {
                const e = await signInWithKakao();
                if (e) setMsg(e);
              }}
            >
              {t.kakao}
            </button>
            {!byMail ? (
              <button className="btn secondary mt-8" onClick={() => setByMail(true)}>
                {t.mail}
              </button>
            ) : (
              <>
                <label className="sub fs-md d-block ta-left mt-16">
                  {t.emailLabel}
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    className="f-input mt-6 mb-12"
                  />
                </label>
                <button
                  className="btn primary"
                  disabled={!email.includes("@")}
                  onClick={async () => setMsg((await sendLoginLink(email)) ?? t.sent)}
                >
                  {t.send}
                </button>
              </>
            )}
            {msg && <p className="fs-md c-green mt-12">{msg}</p>}
            <p className="sub fs-sm mt-16 mb-0">
              {t.agree[0]}
              <Link href="/terms" className="fw-7">
                {t.agree[1]}
              </Link>
              {t.agree[2]}
              <Link href="/privacy" className="fw-7">
                {t.agree[3]}
              </Link>
              {t.agree[4]}
            </p>
          </>
        )}
      </section>
    </main>
  );
}
