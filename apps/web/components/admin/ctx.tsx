"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { AdminError, can, type Role } from "@/lib/api/admin";

// 관리자 화면 공통: 토큰·역할·알림 한 줄·확인 단추.
type Ctx = { token: string; role: Role; say: (s: string) => void; can: (r: Role) => boolean };
const C = createContext<Ctx | null>(null);

export function AdminProvider(props: { token: string; role: Role; children: React.ReactNode }) {
  const [msg, setMsg] = useState("");
  const say = useCallback((s: string) => {
    setMsg(s);
    window.setTimeout(() => setMsg((m) => (m === s ? "" : m)), 2500);
  }, []);
  return (
    <C.Provider
      value={{ token: props.token, role: props.role, say, can: (r) => can(props.role, r) }}
    >
      {props.children}
      {msg && <div className="toast">{msg}</div>}
    </C.Provider>
  );
}

export function useAdmin(): Ctx {
  const v = useContext(C);
  if (!v) throw new Error("AdminProvider 밖");
  return v;
}

export const errText = (e: unknown) =>
  e instanceof AdminError ? e.detail : e instanceof Error ? e.message : String(e);

/** 되돌릴 수 없는 일: 한 번 누르면 「정말 할까요?」로 바뀌고 한 번 더 눌러야 실행. */
export function Confirm(props: {
  label: string;
  ask: string;
  onYes: () => Promise<unknown> | void;
  danger?: boolean;
}) {
  const [open, setOpen] = useState(false);
  if (!open)
    return (
      <button className={`adm-btn${props.danger ? " danger" : ""}`} onClick={() => setOpen(true)}>
        {props.label}
      </button>
    );
  return (
    <span className="adm-confirm">
      <span>{props.ask}</span>
      <button
        className="adm-btn danger"
        onClick={async () => {
          setOpen(false);
          await props.onYes();
        }}
      >
        예
      </button>
      <button className="adm-btn" onClick={() => setOpen(false)}>
        아니오
      </button>
    </span>
  );
}

export const when = (s: string | null | undefined) =>
  s
    ? new Date(s).toLocaleString("ko-KR", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "-";
