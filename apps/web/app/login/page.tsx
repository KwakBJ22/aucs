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
      <section className="section py-28 px-18">
        <h2 className="fs-2xl">{t.title}</h2>
        {session ? (
          <>
            <p className="sub fs-base">{t.loggedIn(session.user.email ?? "")}</p>
            <button
              className="btn bg-gray-chip"

              onClick={() => void signOut()}
            >
              {t.logout}
            </button>
          </>
        ) : (
          <>
            <button className="btn kakao mt-16 mb-8 mx-0" disabled>
              {copy.home.kakao}
            </button>
            <p className="sub ta-center mt-0 mb-20 mx-0">{t.kakaoSoon}</p>
            <label className="sub fs-md">
              {t.emailLabel}
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                className="d-block w-full r-14 b-0 py-0 px-14 fs-base mt-6 mb-12 mx-0 bg-panel c-text"
                style={{ height: 52 }}
              />
            </label>
            <button
              className="btn primary"
              disabled={!email.includes("@")}
              onClick={async () => setMsg((await sendLoginLink(email)) ?? t.sent)}
            >
              {t.send}
            </button>
            {msg && <p className="fs-md c-green mt-12">{msg}</p>}
          </>
        )}
      </section>
    </main>
  );
}
