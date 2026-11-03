"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type Notice } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { Confirm, errText, useAdmin, when } from "./ctx";

const t = copy.admin;

// 6 공지: 쓰기·고치기·내리기. 게시 중인 공지는 홈 맨 위에 한 줄로 보임.
export function NoticesView() {
  const { token, say, can } = useAdmin();
  const [rows, setRows] = useState<Notice[]>([]);
  const [id, setId] = useState<number | undefined>();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [end, setEnd] = useState("");
  const [pinned, setPinned] = useState(false);
  const load = useCallback(() => {
    adminApi
      .notices(token)
      .then(setRows)
      .catch((e) => say(errText(e)));
  }, [token, say]);
  useEffect(load, [load]);
  const reset = () => {
    setId(undefined);
    setTitle("");
    setBody("");
    setEnd("");
    setPinned(false);
  };
  const live = (n: Notice) => !n.end_at || Date.parse(n.end_at) > Date.now();
  return (
    <>
      {can("operator") && (
        <section className="section">
          <h2>{id ? t.noticeEdit : t.noticeNew}</h2>
          <input
            className="adm-input w-full"
            placeholder={t.noticeTitle}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <textarea
            className="adm-input w-full mt-8"
            rows={4}
            placeholder={t.noticeBody}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <div className="adm-line">
            <label className="sub">
              {t.noticeEnd}{" "}
              <input
                type="date"
                className="adm-input"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
            <label className="sub">
              <input
                type="checkbox"
                checked={pinned}
                onChange={(e) => setPinned(e.target.checked)}
              />{" "}
              {t.pinned}
            </label>
            <button
              className="adm-btn primary"
              disabled={title.trim().length < 2}
              onClick={() =>
                adminApi
                  .saveNotice(
                    token,
                    { title, body, pinned, end_at: end ? `${end}T23:59:59+09:00` : null },
                    id,
                  )
                  .then(() => {
                    say(t.done);
                    reset();
                    load();
                  })
                  .catch((e) => say(errText(e)))
              }
            >
              {t.save}
            </button>
            {id && (
              <button className="adm-btn" onClick={reset}>
                {t.cancel}
              </button>
            )}
          </div>
        </section>
      )}
      <section className="section">
        <h2>{t.notices}</h2>
        {rows.length === 0 && <p className="sub">{t.none}</p>}
        {rows.map((n) => (
          <div key={n.notice_id} className="adm-card">
            <div>
              {n.pinned && <span className="chip blue">{t.pinned}</span>} <b>{n.title}</b>{" "}
              <span className={`chip ${live(n) ? "green" : "gray"}`}>
                {live(n) ? t.live : t.ended}
              </span>
            </div>
            <div className="sub">
              {when(n.start_at)} ~ {n.end_at ? when(n.end_at) : t.noEnd}
            </div>
            {can("operator") && live(n) && (
              <div className="adm-line">
                <button
                  className="adm-btn"
                  onClick={() => {
                    setId(n.notice_id);
                    setTitle(n.title);
                    setBody(n.body);
                    setPinned(n.pinned);
                    setEnd(n.end_at ? n.end_at.slice(0, 10) : "");
                  }}
                >
                  {t.edit}
                </button>
                <Confirm
                  label={t.noticeOff}
                  ask={t.noticeOffAsk}
                  onYes={() =>
                    adminApi
                      .endNotice(token, n.notice_id)
                      .then(load)
                      .catch((e) => say(errText(e)))
                  }
                />
              </div>
            )}
          </div>
        ))}
      </section>
    </>
  );
}
