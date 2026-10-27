"use client";

import { useCallback, useEffect, useState } from "react";
import {
  adminApi,
  formatBytes,
  type AdminStatus,
  type Flag,
  type Review,
  type RuleRow,
} from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";

const t = copy.admin;
const box = { border: "1px solid #e5e7eb", borderRadius: 12, padding: 16, margin: "12px 0" };
const th = {
  textAlign: "left" as const,
  color: "#6b7280",
  fontWeight: 500,
  padding: "6px 8px 6px 0",
};
const td = { padding: "6px 8px 6px 0", borderTop: "1px solid #f3f4f6" };

function readToken(): string {
  try {
    return sessionStorage.getItem("aucs_admin") ?? "";
  } catch {
    return "";
  }
}

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [rules, setRules] = useState<RuleRow[]>([]);

  const load = useCallback(async (k: string) => {
    try {
      const [s, r, f, ru] = await Promise.all([
        adminApi.status(k),
        adminApi.review(k),
        adminApi.flags(k),
        adminApi.rules(k),
      ]);
      setStatus(s);
      setReview(r);
      setFlags(f);
      setRules(ru);
      setError("");
      setToken(k);
      try {
        sessionStorage.setItem("aucs_admin", k);
      } catch {
        /* 저장 못 해도 화면은 동작 */
      }
    } catch (e) {
      setError(e instanceof Error && e.message === "denied" ? t.denied : String(e));
      setToken("");
    }
  }, []);

  useEffect(() => {
    const k = readToken();
    if (k) void load(k);
  }, [load]);

  if (!token) {
    return (
      <main style={{ maxWidth: 420, margin: "0 auto", padding: "32px 20px" }}>
        <h1 style={{ fontSize: 24 }}>{t.title}</h1>
        <label>
          {t.tokenLabel}
          <input
            type="password"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            style={{ display: "block", width: "100%", padding: 12, margin: "8px 0", fontSize: 16 }}
          />
        </label>
        <button onClick={() => void load(input)} style={{ padding: "12px 20px", fontSize: 16 }}>
          {t.tokenSave}
        </button>
        {error && <p style={{ color: "#d64545" }}>{error}</p>}
      </main>
    );
  }

  const dbUsed = status ? status.counts.db_bytes / status.db_limit_bytes : 0;
  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
      <h1 style={{ fontSize: 24 }}>{t.title}</h1>

      <section style={box}>
        <h2 style={{ fontSize: 18, marginTop: 0 }}>{t.jobs}</h2>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr>
              <th style={th}>{t.job}</th>
              <th style={th}>{t.lastRun}</th>
              <th style={th}>{t.result}</th>
              <th style={th}>{t.count}</th>
            </tr>
          </thead>
          <tbody>
            {status?.jobs.map((j) => (
              <tr key={j.job_id}>
                <td style={td}>{j.name_ko}</td>
                <td style={td}>{new Date(j.started_at).toLocaleString("ko-KR")}</td>
                <td style={{ ...td, color: j.status === "ok" ? "#1f9d55" : "#d64545" }}>
                  {t.statusName[j.status] ?? j.status}
                  {j.message ? ` · ${j.message}` : ""}
                </td>
                <td style={td}>{j.item_count?.toLocaleString("ko-KR") ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {status && (
          <p style={{ fontSize: 14, color: dbUsed > 0.9 ? "#d64545" : "#6b7280" }}>
            {t.db} {formatBytes(status.counts.db_bytes)} / {formatBytes(status.db_limit_bytes)}
          </p>
        )}
      </section>

      <section style={box}>
        <h2 style={{ fontSize: 18, marginTop: 0 }}>{t.review}</h2>
        {review &&
          review.fields.length + review.signals.length + (review.reports?.length ?? 0) === 0 && (
            <p>{t.reviewEmpty}</p>
          )}
        {(review?.reports?.length ?? 0) > 0 && (
          <>
            <b style={{ fontSize: 14 }}>{t.reportsTitle}</b>
            <ul style={{ paddingLeft: 18, fontSize: 14 }}>
              {review?.reports?.map((r) => (
                <li key={r.report_id}>
                  {r.at} · <a href={`/item/${encodeURIComponent(r.item_id)}`}>{r.item_id}</a> ·{" "}
                  {r.section} · {r.note}
                </li>
              ))}
            </ul>
          </>
        )}
        <ul style={{ paddingLeft: 18, fontSize: 14 }}>
          {review?.signals.map((s) => (
            <li key={`${s.item_id}-${s.title}`}>
              {s.sale_date} · {s.item_id} · {s.title}
            </li>
          ))}
          {review?.fields.map((f) => (
            <li key={f.field_id}>
              {f.case_id} · {f.field} · {f.raw_text}
            </li>
          ))}
        </ul>
      </section>

      <section style={box}>
        <h2 style={{ fontSize: 18, marginTop: 0 }}>{t.flags}</h2>
        {flags.map((f) => (
          <label
            key={f.flag_key}
            style={{ display: "flex", gap: 12, alignItems: "center", minHeight: 44 }}
          >
            <input
              type="checkbox"
              checked={f.enabled}
              onChange={async (e) => {
                const row = await adminApi.setFlag(token, f.flag_key, e.target.checked);
                setFlags((xs) => xs.map((x) => (x.flag_key === row.flag_key ? row : x)));
              }}
            />
            <span>{f.note ?? f.flag_key}</span>
          </label>
        ))}
      </section>

      <section style={box}>
        <h2 style={{ fontSize: 18, marginTop: 0 }}>{t.rules}</h2>
        {rules.length === 0 && <p>{t.rulesEmpty}</p>}
        <ul style={{ paddingLeft: 18, fontSize: 14 }}>
          {rules.map((r) => (
            <li key={`${r.rule_key}-${r.valid_from}`}>
              {r.rule_key} · {r.valid_from}~{r.valid_to ?? ""} · {r.basis}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
