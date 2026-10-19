import Link from "next/link";

// 화면 머리(제목 줄). 휴대폰: 뒤로 · 제목 · 오른쪽 단추 하나. PC: 같은 자리가 화면 제목이 됩니다.
// brand=true 는 탭 첫 화면(휴대폰에서만 「옥스」 글자를 보여 줌).
export function PageHeader({
  title,
  back,
  right,
  sub,
}: {
  title: React.ReactNode;
  back?: string;
  right?: React.ReactNode;
  sub?: React.ReactNode;
}) {
  return (
    <>
      <div className="topbar">
        {back && (
          <Link href={back} aria-label="뒤로" className="tb-back">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="m15 5-7 7 7 7" />
            </svg>
          </Link>
        )}
        <h1 className="brand">{title}</h1>
        <span style={{ flexGrow: 1 }} />
        {right}
      </div>
      {sub && <div className="tb-sub sub">{sub}</div>}
    </>
  );
}
