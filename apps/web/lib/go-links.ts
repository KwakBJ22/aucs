// 바로 가기(11/20 대표님): 옥션원 · 탱크처럼 다 걸지 않고, 그 내용을 확인할 칸 바로 아래에 물건 종류에 맞는 것만.
// 주소 · 지번이 미리 들어가 열리는 것은 11/20 크롬으로 열어 확인한 것만(토지이음 pnu · 카카오 로드뷰 좌표 · KB 지도 좌표).
// 나머지는 그 사이트에 그런 주소가 없거나 확인 못 해 첫 화면으로 가고, 누를 때 물건 주소를 복사해 둠.

export type GoKey =
  | "roadview"
  | "eum"
  | "rt"
  | "naver"
  | "kb"
  | "kapt"
  | "valuemap"
  | "disco"
  | "sbiz"
  | "redev"
  | "price"
  | "iros";

export type GoItem = {
  address: string | null;
  pnu?: string | null;
  lat: number | null;
  lon: number | null;
  usage_kind?: string;
};

// 물건 종류마다 나오는 것(없는 종류는 모든 물건 공통 것만)
const KINDS: Partial<Record<GoKey, string[]>> = {
  rt: ["apt", "officetel", "villa", "house", "land"],
  naver: ["apt", "officetel", "villa"],
  kb: ["apt"],
  kapt: ["apt"],
  valuemap: ["land", "shop"],
  disco: ["land", "shop"],
  sbiz: ["shop"],
  price: ["apt", "villa", "house", "land"],
};

// 인터넷등기소(11/12): 휴대폰 웹은 열람을 앱으로 넘기므로 휴대폰은 처음부터 앱으로.
// 안드로이드는 앱이 있으면 바로 열고 없으면 플레이스토어(kr.go.iros), 아이폰은 앱스토어(있으면 「열기」).
const PLAY = "https://play.google.com/store/apps/details?id=kr.go.iros";
export const IROS_HOME = "https://www.iros.go.kr/index.jsp";
export const iros = () => {
  const ua = navigator.userAgent;
  if (/android/i.test(ua))
    return `intent:#Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;package=kr.go.iros;S.browser_fallback_url=${encodeURIComponent(PLAY)};end`;
  if (/iphone|ipad|ipod/i.test(ua)) return "https://apps.apple.com/kr/app/id952161112";
  return IROS_HOME;
};

const HOME: Record<GoKey, string> = {
  roadview: "https://map.kakao.com",
  eum: "https://www.eum.go.kr/web/ar/lu/luLandDet.jsp",
  rt: "https://rt.molit.go.kr/",
  naver: "https://new.land.naver.com/",
  kb: "https://kbland.kr/map",
  kapt: "https://www.k-apt.go.kr/web/main/index.do",
  valuemap: "https://www.valueupmap.com/",
  disco: "https://www.disco.re/",
  sbiz: "https://sg.sbiz.or.kr/",
  redev: "https://cleanup.seoul.go.kr/",
  price: "https://www.realtyprice.kr/notice/main/main.do",
  iros: IROS_HOME,
};

export type GoLink = { key: GoKey; href: string; filled: boolean };

/** 이 물건에 보일 바로 가기 하나 — 안 맞는 종류 · 재료가 없으면 null. filled: 주소가 미리 들어가 열림 */
export function goLink(k: GoKey, d: GoItem): GoLink | null {
  const kinds = KINDS[k];
  if (kinds && !kinds.includes(d.usage_kind ?? "")) return null;
  const at = d.lat != null && d.lon != null;
  switch (k) {
    case "roadview":
      return at
        ? { key: k, href: `https://map.kakao.com/link/roadview/${d.lat},${d.lon}`, filled: true }
        : null;
    case "eum":
      return d.pnu
        ? {
            key: k,
            href: `${HOME.eum}?pnu=${d.pnu}&mode=search&isNoScr=script&selGbn=umd`,
            filled: true,
          }
        : null;
    case "kb":
      return at ? { key: k, href: `${HOME.kb}?xy=${d.lat},${d.lon},18`, filled: true } : null;
    case "redev":
      // 서울 정비사업 정보몽땅만(경기 · 인천은 구역으로 바로 가는 곳을 아직 못 찾음)
      return (d.address ?? "").startsWith("서울")
        ? { key: k, href: HOME.redev, filled: false }
        : null;
    default:
      return { key: k, href: HOME[k], filled: false };
  }
}
