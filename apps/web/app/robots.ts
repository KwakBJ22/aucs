import type { MetadataRoute } from "next";

// 검색 로봇 안내(11/17): 홈 · 찾기 · 모아 보기 · 아카데미 · 공지 · 약관은 검색에 나오게,
// 회원 화면 · 관리자 · 물건 상세 · 전문가 표는 들어오지 않게(상세는 로그인해야 보여 검색에 쓸 것이 없음).
// 지키지 않는 로봇은 서버의 로그인 · 횟수 한도(api services/access)로 막음.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/admin",
        "/me",
        "/more",
        "/watch",
        "/notifications",
        "/points",
        "/compare",
        "/login",
        "/item/",
        "/pro/",
      ],
    },
  };
}
