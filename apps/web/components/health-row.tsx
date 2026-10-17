import { copy } from "@/lib/copy.ko";
import type { HealthState } from "@/lib/api/health";

const color: Record<HealthState, string> = {
  checking: "#8a8f98",
  ok: "#1f9d55",
  fail: "#d64545",
};

export function HealthRow({ label, state }: { label: string; state: HealthState }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 0" }}>
      <span>{label}</span>
      <span style={{ color: color[state], fontWeight: 600 }}>{copy.health[state]}</span>
    </div>
  );
}
