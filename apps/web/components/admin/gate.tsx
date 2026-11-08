"use client";

import { Delayed, SkHeader, SkRows } from "@/components/skeleton";
import Link from "next/link";
import { useEffect, useState } from "react";
import { adminApi, type Role } from "@/lib/api/admin";
import { supabase, useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.admin;

// 관리자 들어오기(11/2): 옥스 로그인 → 관리자 표 확인 → 2단계 인증(OTP 앱). 통과하면 children(token, role).
export function AdminGate(props: { children: (token: string, role: Role) => React.ReactNode }) {
  const { session, ready } = useSession();
  const [me, setMe] = useState<{ role: Role; mfa: boolean } | null>(null);
  const [state, setState] = useState<"loading" | "denied" | "ok">("loading");
  const token = session?.access_token ?? "";

  useEffect(() => {
    if (!token) return;
    adminApi
      .me(token)
      .then((m) => {
        setMe(m);
        setState("ok");
      })
      .catch(() => setState("denied"));
  }, [token]);

  if (!ready)
    return (
      <main className="page">
        <Delayed>
          <SkHeader />
          <SkRows n={6} />
        </Delayed>
      </main>
    );
  if (!session)
    return (
      <main className="adm-gate">
        <h1>{t.title}</h1>
        <p className="sub">{t.needLogin}</p>
        <Link href="/login" className="btn primary">
          {t.login}
        </Link>
      </main>
    );
  if (state === "denied")
    return (
      <main className="adm-gate">
        <h1>{t.title}</h1>
        <p className="sub">{t.denied}</p>
      </main>
    );
  if (!me)
    return (
      <main className="page">
        <Delayed>
          <SkHeader />
          <SkRows n={6} />
        </Delayed>
      </main>
    );
  if (!me.mfa) return <Mfa />;
  return <>{props.children(token, me.role)}</>;
}

function Mfa() {
  const [factor, setFactor] = useState<string | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!supabase) return;
    void (async () => {
      const { data } = await supabase.auth.mfa.listFactors();
      const ok = data?.totp.find((f) => f.status === "verified");
      if (ok) return setFactor(ok.id);
      for (const f of data?.all ?? [])
        if (f.status === "unverified") await supabase.auth.mfa.unenroll({ factorId: f.id });
      const { data: en, error } = await supabase.auth.mfa.enroll({
        factorType: "totp",
        friendlyName: `옥스 관리자 ${Date.now()}`,
      });
      if (error || !en) return setErr(error?.message ?? t.mfaFail);
      setFactor(en.id);
      setQr(en.totp.qr_code);
    })();
  }, []);

  const verify = async () => {
    if (!supabase || !factor) return;
    setErr("");
    const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId: factor, code });
    if (error) return setErr(t.mfaWrong);
    await supabase.auth.refreshSession(); // aal2 토큰으로 바뀜 → 화면이 다시 확인
  };

  return (
    <main className="adm-gate">
      <h1>{t.mfaTitle}</h1>
      {qr ? (
        <>
          <p className="sub">{t.mfaEnroll}</p>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={qr} alt="QR" className="adm-qr" />
        </>
      ) : (
        <p className="sub">{t.mfaAsk}</p>
      )}
      <input
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
        className="adm-input adm-code"
        placeholder="000000"
      />
      <button className="btn primary" disabled={code.length !== 6} onClick={() => void verify()}>
        {t.mfaGo}
      </button>
      {err && <p className="adm-err">{err}</p>}
    </main>
  );
}
