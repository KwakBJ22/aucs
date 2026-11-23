"use client";

import { useCallback, useEffect, useState } from "react";
import { AdminGate } from "@/components/admin/gate";
import { AdminProvider } from "@/components/admin/ctx";
import { AppraisalGet } from "@/components/admin/appraisal-get";
import { DocUpload } from "@/components/admin/doc-upload";
import { BroadcastView } from "@/components/admin/broadcasts";
import { JobsView } from "@/components/admin/jobs";
import { MembersView } from "@/components/admin/members";
import { NoticesView } from "@/components/admin/notices";
import { PlansView } from "@/components/admin/plans";
import { PointsReview } from "@/components/admin/points-review";
import { PredictView } from "@/components/admin/predict";
import { ReviewView } from "@/components/admin/review";
import { SettingsView } from "@/components/admin/settings";
import { StatsView } from "@/components/admin/stats";
import { TodayView } from "@/components/admin/today";
import { copy } from "@/lib/copy.ko";
import { toTop } from "@/lib/scroll";

const t = copy.admin;
const MENUS = [
  "today",
  "jobs",
  "review",
  "upload",
  "members",
  "notices",
  "plans",
  "predict",
  "stats",
  "settings",
] as const;
type Menu = (typeof MENUS)[number];

const pick = (x: string | null): Menu =>
  (MENUS as readonly string[]).includes(x ?? "") ? (x as Menu) : "today";

// 관리자 모드(11/2 1단계): 왼쪽 메뉴 20 · 내용 80 (휴대폰은 위에 메뉴 줄)
// 메뉴마다 주소(?m=members) — 새로고침 · 뒤로 가기 · 링크 보내기가 그 메뉴로(11/23)
export default function AdminPage() {
  const [m, setM] = useState<Menu>("today");
  useEffect(() => {
    const read = () => setM(pick(new URLSearchParams(window.location.search).get("m")));
    read();
    window.addEventListener("popstate", read);
    return () => window.removeEventListener("popstate", read);
  }, []);
  const go = useCallback((x: string) => {
    const k = pick(x);
    setM(k);
    window.history.pushState(null, "", k === "today" ? "/admin" : `/admin?m=${k}`);
    toTop();
  }, []);
  return (
    <AdminGate>
      {(token, role) => (
        <AdminProvider token={token} role={role}>
          <main className="adm">
            <nav className="adm-menu">
              {MENUS.map((k) => (
                <button key={k} className={m === k ? "on" : ""} onClick={() => go(k)}>
                  {t.menu[k]}
                </button>
              ))}
              <span className="sub adm-role">{t.roleName[role]}</span>
            </nav>
            <div className="adm-body">
              <h1 className="adm-h1">{t.menu[m]}</h1>
              {m === "today" && <TodayView go={go} />}
              {m === "jobs" && <JobsView />}
              {m === "review" && (
                <>
                  <PointsReview />
                  <AppraisalGet />
                  <ReviewView />
                </>
              )}
              {m === "upload" && <DocUpload />}
              {m === "members" && <MembersView />}
              {m === "notices" && (
                <>
                  <BroadcastView />
                  <NoticesView />
                </>
              )}
              {m === "plans" && <PlansView />}
              {m === "predict" && <PredictView />}
              {m === "stats" && <StatsView />}
              {m === "settings" && <SettingsView />}
            </div>
          </main>
        </AdminProvider>
      )}
    </AdminGate>
  );
}
