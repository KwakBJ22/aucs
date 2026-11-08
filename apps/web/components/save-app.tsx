"use client";

import { useEffect, useState } from "react";
import {
  canPrompt,
  isStandalone,
  onInstallChange,
  platform,
  promptInstall,
  type Platform,
} from "@/lib/install";
import { copy } from "@/lib/copy.ko";

const t = copy.install;

// 「홈 화면에 두기」·「즐겨찾기 추가」 두 버튼(11/8). 브라우저가 설치 창을 주면 바로 띄우고,
// 아니면(아이폰 사파리 등) 어디를 누르면 되는지 한 줄로 알려 줌. 즐겨찾기는 브라우저가
// 사이트에서 직접 추가하는 길을 막아 두어 단축키·메뉴를 알려 줌.
export function SaveApp({ className = "" }: { className?: string }) {
  const [, redraw] = useState(0);
  const [os, setOs] = useState<Platform | null>(null);
  const [installed, setInstalled] = useState(false);
  const [how, setHow] = useState("");
  useEffect(() => {
    setOs(platform());
    setInstalled(isStandalone());
    return onInstallChange(() => redraw((n) => n + 1));
  }, []);
  if (!os) return null;

  const addHome = async () => {
    if (await promptInstall()) return setHow("");
    setHow(t.how[os]);
  };
  const addMark = () => setHow(t.mark[os]);

  return (
    <section className={`section ${className}`}>
      <h2>{t.boxTitle}</h2>
      <p className="sub fs-md mt-4">{t.why}</p>
      <div className="btn-pair mt-12">
        {!installed && (
          <button className={`btn ${canPrompt() ? "primary" : "secondary"}`} onClick={addHome}>
            {t.home}
          </button>
        )}
        <button className="btn secondary" onClick={addMark}>
          {t.bookmark}
        </button>
      </div>
      {how && <div className="bg-panel r-14 p-12 mt-12 fs-md lh-16">{how}</div>}
    </section>
  );
}
