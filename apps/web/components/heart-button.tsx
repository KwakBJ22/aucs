"use client";

import { useWatch } from "./watch-context";
import { copy } from "@/lib/copy.ko";

export function HeartButton({ id }: { id: string }) {
  const { ids, toggle } = useWatch();
  const on = ids.has(id);
  return (
    <button
      aria-label={on ? copy.watch.remove : copy.watch.add}
      onClick={() => void toggle(id)}
      style={{
        border: 0,
        background: "none",
        padding: 4,
        minWidth: 44,
        minHeight: 44,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "flex-end",
      }}
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill={on ? "var(--red)" : "none"}
        stroke={on ? "var(--red)" : "var(--faint)"}
        strokeWidth="1.8"
        aria-hidden="true"
      >
        <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
      </svg>
    </button>
  );
}
