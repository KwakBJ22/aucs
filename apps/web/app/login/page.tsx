"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  nextPath,
  sendLoginLink,
  signInWithKakao,
  signOut,
  userLabel,
  useSession,
  verifyLoginCode,
} from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.loginPage;

export default function Login() {
  const { session } = useSession();
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [byMail, setByMail] = useState(false);
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const router = useRouter();

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
                  className={sent ? "btn secondary" : "btn primary"}
                  disabled={!email.includes("@")}
                  onClick={async () => {
                    const e = await sendLoginLink(email);
                    setMsg(e ?? t.sent);
                    if (!e) setSent(true);
                  }}
                >
                  {sent ? t.resend : t.send}
                </button>
                {/* 메일 속 숫자를 이 창에 넣으면 바로 로그인(링크가 다른 브라우저에서 열려도 됨, 11/28) */}
                {sent && (
                  <>
                    <label className="sub fs-md d-block ta-left mt-16">
                      {t.codeLabel}
                      <input
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        value={code}
                        onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 10))}
                        className="f-input mt-6 mb-12"
                      />
                    </label>
                    <button
                      className="btn primary"
                      disabled={code.length < 6}
                      onClick={async () => {
                        const e = await verifyLoginCode(email, code);
                        if (e) setMsg(t.codeWrong);
                        else router.replace(nextPath());
                      }}
                    >
                      {t.codeGo}
                    </button>
                  </>
                )}
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
