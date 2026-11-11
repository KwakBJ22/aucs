"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { adminApi, pointReviewPdf, type PointReview } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { errText, useAdmin, when } from "./ctx";

const t = copy.admin.points;

// 포인트 벌기(11/12): 손님이 올린 감정평가서 중 글이 없어 사건번호를 못 읽은 것 — 보고 맞으면 넣고 포인트
export function PointsReview() {
  const { token, say, can } = useAdmin();
  const [rows, setRows] = useState<PointReview[] | null>(null);
  const load = useCallback(() => {
    adminApi
      .pointReviews(token)
      .then(setRows)
      .catch((e) => say(errText(e)));
  }, [token, say]);
  useEffect(load, [load]);
  if (!rows?.length) return null;
  const decide = (id: number, ok: boolean) =>
    adminApi
      .decidePoint(token, id, ok)
      .then(load)
      .catch((e) => say(errText(e)));
  return (
    <section className="section">
      <h2>{t.title(rows.length)}</h2>
      {rows.map((r) => (
        <div key={r.contrib_id} className="adm-card">
          <div className="sub">
            <Link href={`/item/${encodeURIComponent(r.item_id)}`} target="_blank">
              {r.item_id}
            </Link>{" "}
            · {when(r.created_at)}
          </div>
          <div className="adm-line">
            <button
              className="adm-btn"
              onClick={() =>
                pointReviewPdf(token, r.contrib_id)
                  .then((u) => window.open(u, "_blank"))
                  .catch((e) => say(errText(e)))
              }
            >
              {t.open}
            </button>
            {can("operator") && (
              <>
                <button className="adm-btn" onClick={() => decide(r.contrib_id, true)}>
                  {t.ok}
                </button>
                <button className="adm-btn" onClick={() => decide(r.contrib_id, false)}>
                  {t.no}
                </button>
              </>
            )}
          </div>
        </div>
      ))}
    </section>
  );
}
