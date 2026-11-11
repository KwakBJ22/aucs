"use client";

import { useState } from "react";
import { AdminGate } from "@/components/admin/gate";
import { AdminProvider } from "@/components/admin/ctx";
import { JobsView } from "@/components/admin/jobs";
import { MembersView } from "@/components/admin/members";
import { NoticesView } from "@/components/admin/notices";
import { PointsReview } from "@/components/admin/points-review";
import { ReviewView } from "@/components/admin/review";
import { SettingsView } from "@/components/admin/settings";
import { StatsView } from "@/components/admin/stats";
import { TodayView } from "@/components/admin/today";
import { copy } from "@/lib/copy.ko";

const t = copy.admin;
const MENUS = ["today", "jobs", "review", "members", "notices", "stats", "settings"] as const;
type Menu = (typeof MENUS)[number];

// 관리자 모드(11/2 1단계): 왼쪽 메뉴 20 · 내용 80 (휴대폰은 위에 메뉴 줄)
export default function AdminPage() {
  const [m, setM] = useState<Menu>("today");
  const go = (x: string) => setM((MENUS as readonly string[]).includes(x) ? (x as Menu) : "today");
  return (
    <AdminGate>
      {(token, role) => (
        <AdminProvider token={token} role={role}>
          <main className="adm">
            <nav className="adm-menu">
              {MENUS.map((k) => (
                <button key={k} className={m === k ? "on" : ""} onClick={() => setM(k)}>
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
                  <ReviewView />
                </>
              )}
              {m === "members" && <MembersView />}
              {m === "notices" && <NoticesView />}
              {m === "stats" && <StatsView />}
              {m === "settings" && <SettingsView />}
            </div>
          </main>
        </AdminProvider>
      )}
    </AdminGate>
  );
}
