import { copy } from "@/lib/copy.ko";
import type { HealthState } from "@/lib/api/health";

const color: Record<HealthState, string> = {
  checking: "var(--faint)",
  ok: "var(--green)",
  fail: "var(--red)",
};

export function HealthRow({ label, state }: { label: string; state: HealthState }) {
  return (
    <div className="d-flex jc-between py-12 px-0">
      <span>{label}</span>
      <span className="fw-6" style={{ color: color[state] }}>
        {copy.health[state]}
      </span>
    </div>
  );
}
