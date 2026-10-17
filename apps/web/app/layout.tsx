import type { Metadata, Viewport } from "next";
import { copy } from "@/lib/copy.ko";

export const metadata: Metadata = { title: copy.appName, manifest: "/manifest.json" };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#ffffff" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body
        style={{
          margin: 0,
          fontFamily: "system-ui, -apple-system, 'Apple SD Gothic Neo', sans-serif",
          background: "#fff",
          color: "#111",
        }}
      >
        {children}
      </body>
    </html>
  );
}
