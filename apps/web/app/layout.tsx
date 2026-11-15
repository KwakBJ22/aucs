import type { Metadata, Viewport } from "next";
// 글꼴(11/4): Pretendard를 사이트에 같이 실어 어느 기기에서나 같은 모양. 쓰는 글자 묶음만 받아 가벼움
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";
import { copy } from "@/lib/copy.ko";
import { Providers } from "@/components/providers";

// 아이폰(11/8): 홈 화면에 둔 옥스가 앱처럼 열리게(appleWebApp), 사건번호·금액 숫자를 전화번호로
// 잘못 알아 파란 링크로 바꾸지 않게(formatDetection), 노치·홈 막대 자리까지 쓰고 안쪽은 safe-area로 띄움(viewportFit)
// 카톡 · 문자에 주소를 붙이면 뜨는 카드(11/16): 그림 1200×630(카톡은 가운데 2:1 로 잘라 보여 줌)
export const metadata: Metadata = {
  metadataBase: new URL("https://aucs.co.kr"),
  title: copy.siteTitle,
  description: copy.siteDesc,
  openGraph: {
    type: "website",
    siteName: copy.siteTitle,
    title: copy.siteTitle,
    description: copy.siteDesc,
    url: "/",
    locale: "ko_KR",
    images: [{ url: "/brand/og.png", width: 1200, height: 630, alt: copy.siteTitle }],
  },
  twitter: { card: "summary_large_image", images: ["/brand/og.png"] },
  manifest: "/manifest.json",
  appleWebApp: { capable: true, title: "옥스경매", statusBarStyle: "default" },
  formatDetection: { telephone: false, email: false, address: false },
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f4f5f7",
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
