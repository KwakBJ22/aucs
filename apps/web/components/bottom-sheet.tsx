"use client";

import { useEffect } from "react";

// 아래에서 올라오는 창 하나(11/23 — 용어 · 앱 설치 · 찾기 조건이 같이 씀).
// 뒤를 어둡게, 뒤를 누르거나 Esc 면 닫힘. foot 은 창 맨 아래에 붙는 단추 줄.
export function BottomSheet({
  label,
  onClose,
  children,
  foot,
  className = "",
}: {
  label: string;
  onClose: () => void;
  children: React.ReactNode;
  foot?: React.ReactNode;
  className?: string;
}) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="sheet-dim" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={label}
        onClick={(e) => e.stopPropagation()}
        className={`sheet sheet-box ${className}`.trim()}
      >
        <div className="sheet-handle" />
        {children}
        {foot && <div className="sheet-foot">{foot}</div>}
      </div>
    </div>
  );
}
