"use client";

import { PageHeader } from "@/components/layout/page-header";
import { useState } from "react";
import { sendLoginLink, signOut, useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.loginPage;

export default function Login() {
  const { session } = useSession();
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");

  return (
    <main className="page narrow">
      <PageHeader title="" back="/home" />
      <section className="section" style={{ padding: "28px 18px" }}>
        <h2 style={{ fontSize: 22 }}>{t.title}</h2>
        {session ? (
          <>
            <p className="sub" style={{ fontSize: 15 }}>
              {t.loggedIn(session.user.email ?? "")}
            </p>
            <button
              className="btn"
              style={{ background: "var(--gray-chip)" }}
              onClick={() => void signOut()}
            >
              {t.logout}
            </button>
          </>
        ) : (
          <>
            <button className="btn kakao" disabled style={{ margin: "16px 0 8px" }}>
              {copy.home.kakao}
            </button>
            <p className="sub" style={{ textAlign: "center", margin: "0 0 20px" }}>
              {t.kakaoSoon}
            </p>
            <label className="sub" style={{ fontSize: 14 }}>
              {t.emailLabel}
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                style={{
                  display: "block",
                  width: "100%",
                  height: 52,
                  borderRadius: 12,
                  border: "1px solid var(--line)",
                  padding: "0 14px",
                  fontSize: 16,
                  margin: "6px 0 12px",
                  background: "var(--bg)",
                  color: "var(--text)",
                }}
              />
            </label>
            <button
              className="btn primary"
              disabled={!email.includes("@")}
              onClick={async () => setMsg((await sendLoginLink(email)) ?? t.sent)}
            >
              {t.send}
            </button>
            {msg && <p style={{ fontSize: 14, color: "var(--green)", marginTop: 12 }}>{msg}</p>}
          </>
        )}
      </section>
    </main>
  );
}
