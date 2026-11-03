"use client";

import { useCallback, useEffect, useState } from "react";
import {
  adminApi,
  type AdminRow,
  type AuditRow,
  type DongAlias,
  type Flag,
  type Role,
  type RuleRow,
} from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { Confirm, errText, useAdmin, when } from "./ctx";

const t = copy.admin;

// 8 설정: 기준표(버전·검토) · 공개 설정 · 바뀐 동 이름 · 관리자 · 감사 기록
export function SettingsView() {
  const { token, say, can } = useAdmin();
  const [rules, setRules] = useState<RuleRow[]>([]);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [dongs, setDongs] = useState<DongAlias[]>([]);
  const [admins, setAdmins] = useState<AdminRow[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [ver, setVer] = useState<{
    key: string;
    from: string;
    value: string;
    basis: string;
  } | null>(null);
  const [dong, setDong] = useState<DongAlias>({
    sido: "",
    city: "",
    old_name: "",
    new_name: "",
    changed_on: null,
  });
  const [mail, setMail] = useState("");
  const [role, setRole] = useState<Role>("operator");
  const owner = can("owner");
  const load = useCallback(() => {
    adminApi
      .screen(token, "settings")
      .then((x) => {
        setRules(x.rules);
        setFlags(x.flags);
        setDongs(x.dongs);
        setAdmins(x.admins);
        setAudit(x.audit);
      })
      .catch((e) => say(errText(e)));
  }, [token, say]);
  useEffect(load, [load]);
  const run = (p: Promise<unknown>) =>
    p
      .then(() => {
        say(t.done);
        load();
      })
      .catch((e) => say(errText(e)));
  const latest = rules.filter((r, i) => rules.findIndex((x) => x.rule_key === r.rule_key) === i);

  return (
    <>
      <section className="section">
        <h2>{t.rules}</h2>
        {latest.map((r) => (
          <div key={r.rule_key} className="adm-card">
            <div>
              <b>{r.rule_key}</b> <span className="sub">{t.ruleFrom(r.valid_from)}</span>{" "}
              <span className={`chip ${r.reviewed_at ? "green" : "orange"}`}>
                {r.reviewed_at ? t.reviewed : t.notReviewed}
              </span>
            </div>
            <div className="sub adm-msg">{JSON.stringify(r.value)}</div>
            <div className="sub">{r.basis}</div>
            {owner && (
              <div className="adm-line">
                {!r.reviewed_at && (
                  <button
                    className="adm-btn"
                    onClick={() => run(adminApi.ruleReviewed(token, r.rule_key, r.valid_from))}
                  >
                    {t.reviewDone}
                  </button>
                )}
                <button
                  className="adm-btn"
                  onClick={() =>
                    setVer({
                      key: r.rule_key,
                      from: "",
                      value: JSON.stringify(r.value),
                      basis: r.basis,
                    })
                  }
                >
                  {t.newVersion}
                </button>
              </div>
            )}
            {ver?.key === r.rule_key && (
              <div className="adm-detail">
                <label className="sub">
                  {t.validFrom}{" "}
                  <input
                    type="date"
                    className="adm-input"
                    value={ver.from}
                    onChange={(e) => setVer({ ...ver, from: e.target.value })}
                  />
                </label>
                <textarea
                  className="adm-input w-full"
                  rows={3}
                  value={ver.value}
                  onChange={(e) => setVer({ ...ver, value: e.target.value })}
                />
                <input
                  className="adm-input w-full"
                  placeholder={t.basis}
                  value={ver.basis}
                  onChange={(e) => setVer({ ...ver, basis: e.target.value })}
                />
                <div className="adm-line">
                  <button
                    className="adm-btn primary"
                    disabled={!ver.from}
                    onClick={() => {
                      let v: unknown;
                      try {
                        v = JSON.parse(ver.value);
                      } catch {
                        return say(t.badJson);
                      }
                      void run(
                        adminApi
                          .newRule(token, ver.key, ver.from, v, ver.basis)
                          .then(() => setVer(null)),
                      );
                    }}
                  >
                    {t.save}
                  </button>
                  <button className="adm-btn" onClick={() => setVer(null)}>
                    {t.cancel}
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </section>

      <section className="section">
        <h2>{t.flags}</h2>
        {flags.map((f) => (
          <label key={f.flag_key} className="adm-row">
            <span>{f.note ?? f.flag_key}</span>
            <input
              type="checkbox"
              checked={f.enabled}
              disabled={!owner}
              onChange={(e) =>
                adminApi
                  .setFlag(token, f.flag_key, e.target.checked)
                  .then((row) =>
                    setFlags((xs) => xs.map((x) => (x.flag_key === row.flag_key ? row : x))),
                  )
                  .catch((x) => say(errText(x)))
              }
            />
          </label>
        ))}
      </section>

      <section className="section">
        <h2>{t.dongs}</h2>
        {dongs.map((d) => (
          <div key={`${d.sido}${d.city}${d.old_name}`} className="adm-row sub">
            <span>
              {d.sido} {d.city}
            </span>
            <span>
              {d.old_name} → {d.new_name}
            </span>
            <span>{d.changed_on ?? ""}</span>
          </div>
        ))}
        {can("operator") && (
          <div className="adm-line">
            {(["sido", "city", "old_name", "new_name"] as const).map((k) => (
              <input
                key={k}
                className="adm-input adm-short"
                placeholder={t.dongPh[k]}
                value={dong[k]}
                onChange={(e) => setDong({ ...dong, [k]: e.target.value })}
              />
            ))}
            <button
              className="adm-btn"
              disabled={!dong.sido || !dong.city || !dong.old_name || !dong.new_name}
              onClick={() =>
                run(
                  adminApi
                    .addDong(token, dong)
                    .then(() =>
                      setDong({ sido: "", city: "", old_name: "", new_name: "", changed_on: null }),
                    ),
                )
              }
            >
              {t.add}
            </button>
          </div>
        )}
      </section>

      <section className="section">
        <h2>{t.admins}</h2>
        {admins.map((a) => (
          <div key={a.user_id} className="adm-row">
            <span>{a.email}</span>
            <span className="chip blue">{t.roleName[a.role]}</span>
            {owner && (
              <Confirm
                danger
                label={t.remove}
                ask={t.removeAsk}
                onYes={() => run(adminApi.removeAdmin(token, a.user_id))}
              />
            )}
          </div>
        ))}
        {owner && (
          <div className="adm-line">
            <input
              className="adm-input"
              placeholder={t.adminEmail}
              value={mail}
              onChange={(e) => setMail(e.target.value)}
            />
            <select
              className="adm-input"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              {(["operator", "viewer", "owner"] as const).map((r) => (
                <option key={r} value={r}>
                  {t.roleName[r]}
                </option>
              ))}
            </select>
            <button
              className="adm-btn"
              disabled={!mail.includes("@")}
              onClick={() => run(adminApi.addAdmin(token, mail, role).then(() => setMail("")))}
            >
              {t.add}
            </button>
          </div>
        )}
      </section>

      {owner && (
        <section className="section">
          <h2>{t.audit}</h2>
          {audit.length === 0 && <p className="sub">{t.none}</p>}
          {audit.map((a) => (
            <div key={a.audit_id} className="adm-row sub">
              <span>{when(a.at)}</span>
              <span>{a.actor}</span>
              <span className="ellipsis">
                {t.actionName[a.action] ?? a.action} · {a.target}
                {a.note ? ` · ${a.note}` : ""}
              </span>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
