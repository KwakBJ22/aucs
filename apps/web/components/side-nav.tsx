"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { copy } from "@/lib/copy.ko";

const t = copy.side;
const BASIC = ["home", "find", "watch", "me"] as const;

// PC(넓은 화면) 왼쪽 메뉴: 기본 4 + 전문가 5 + 아래 전체. 휴대폰에서는 숨고 하단 탭을 씁니다.
export function SideNav() {
  const path = usePathname();
  const on = (href: string) => (path.startsWith(href) ? "on" : "");
  return (
    <nav className="sidenav">
      <Link href="/home" className="brand side-brand">
        {copy.appName}
      </Link>
      {BASIC.map((k) => (
        <Link key={k} href={`/${k}`} className={on(`/${k}`)}>
          {copy.tabs[k]}
        </Link>
      ))}
      <div className="side-head">{t.pro}</div>
      {t.proItems.map((x) =>
        x.ready ? (
          <Link key={x.href} href={x.href} className={on(x.href)}>
            {x.name}
          </Link>
        ) : (
          <span key={x.href} className="side-off">
            {x.name}
            <small>{t.soon}</small>
          </span>
        ),
      )}
      <Link href="/more" className={`side-all ${on("/more")}`}>
        {copy.tabs.more}
      </Link>
    </nav>
  );
}
