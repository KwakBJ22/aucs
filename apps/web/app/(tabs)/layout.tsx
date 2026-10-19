import { AppShell } from "@/components/layout/app-shell";
import { WatchProvider } from "@/components/watch-context";

export default function TabsLayout({ children }: { children: React.ReactNode }) {
  return (
    <WatchProvider>
      <AppShell>{children}</AppShell>
    </WatchProvider>
  );
}
