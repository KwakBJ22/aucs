"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { copy } from "@/lib/copy.ko";

// 용어 설명 창(할 일 5): 어려운 말에 점선 밑줄 → 누르면 아래에서 설명이 올라옴(바텀시트). 화면 이동 없음.
const TERMS: [string, string][] = [...copy.guide.words, ...copy.terms.extra];
const NAMES = TERMS.map(([w]) => w).sort((a, b) => b.length - a.length); // 긴 말부터(「배당요구 종기」 > 「배당」)

function Sheet({ word, text, onClose }: { word: string; text: string; onClose: () => void }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 60, background: "rgba(0,0,0,0.35)" }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={word}
        onClick={(e) => e.stopPropagation()}
        className="term-sheet sheet pos-absolute my-0 mx-auto"
        style={{ left: 0, right: 0, bottom: 0, maxWidth: 560 }}
      >
        <div className="sheet-handle" />
        <div className="d-flex jc-between ai-center">
          <b className="fs-lg">{word}</b>
          <button onClick={onClose} className="btn secondary sm">
            {copy.terms.close}
          </button>
        </div>
        <p className="fs-base lh-16 mt-6 mb-12 mx-0">{text}</p>
        <Link href="/guide" className="link" onClick={onClose}>
          {copy.terms.more}
        </Link>
      </div>
    </div>
  );
}

export function Term({ word, children }: { word: string; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const text = TERMS.find(([w]) => w === word)?.[1];
  if (!text) return <>{children ?? word}</>;
  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
        className="link in term"
      >
        {children ?? word}
      </button>
      {open && <Sheet word={word} text={text} onClose={() => setOpen(false)} />}
    </>
  );
}

/** 글 안의 첫 용어 하나만 밑줄(여러 개면 산만해서). 용어가 없으면 글 그대로. */
export function Termed({ text }: { text: string }) {
  for (const w of NAMES) {
    const i = text.indexOf(w);
    if (i >= 0)
      return (
        <>
          {text.slice(0, i)}
          <Term word={w} />
          {text.slice(i + w.length)}
        </>
      );
  }
  return <>{text}</>;
}
