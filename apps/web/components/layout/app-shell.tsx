import { PcHeader } from "./pc-header";
import { PcFooter } from "./pc-footer";
import { MobileTabbar } from "./mobile-tabbar";

// 모든 화면의 틀: 머리 + 본문 + 바닥. 화면 파일에는 본문만 둡니다.
// PC(1024px 이상) = 상단 메뉴 + 바닥, 휴대폰 = 하단 탭. 어느 쪽을 보일지는 CSS가 정함.
export function AppShell({
  children,
  admin = false,
}: {
  children: React.ReactNode;
  admin?: boolean;
}) {
  return (
    <div className="app-shell">
      <PcHeader admin={admin} />
      <div className="shell">{children}</div>
      <PcFooter />
      {!admin && <MobileTabbar />}
    </div>
  );
}
