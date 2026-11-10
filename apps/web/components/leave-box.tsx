"use client";

import { useState } from "react";
import { meApi } from "@/lib/api/me";
import { signOut } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.leave;

// 회원 탈퇴(11/1): 되돌릴 수 없어서 「탈퇴」를 직접 쳐야 단추가 켜짐
export function LeaveBox({ token }: { token: string }) {
  const [open, setOpen] = useState(false);
  const [word, setWord] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!open)
    return (
      <button className="menu-row w-full b-0 bg-none ta-left" onClick={() => setOpen(true)}>
        <span className="sub">{t.open}</span>
        <span />
      </button>
    );
  return (
    <div className="bg-panel r-14 p-12 mt-8">
      <b className="fs-md">{t.title}</b>
      <p className="sub fs-sm mt-4 mb-8 mx-0">{t.what}</p>
      <input
        value={word}
        onChange={(e) => setWord(e.target.value)}
        placeholder={t.type}
        className="w-full fs-base py-8 px-10 b-0 r-14 bg-bg c-inherit"
      />
      <div className="btn-pair mt-10">
        <button className="btn secondary md" onClick={() => setOpen(false)}>
          {t.cancel}
        </button>
        <button
          className="btn danger md"
          disabled={word.trim() !== t.word || busy}
          onClick={() => {
            setBusy(true);
            meApi
              .deleteAccount(token)
              .then(() => signOut())
              .then(() => (window.location.href = "/home"))
              .catch(() => {
                setErr(t.failed);
                setBusy(false);
              });
          }}
        >
          {t.go}
        </button>
      </div>
      {err && <p className="c-red fs-sm mb-0">{err}</p>}
    </div>
  );
}
