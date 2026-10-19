import { SideNav } from "@/components/side-nav";
import { TabBar } from "@/components/tab-bar";
import { WatchProvider } from "@/components/watch-context";

export default function TabsLayout({ children }: { children: React.ReactNode }) {
  return (
    <WatchProvider>
      <SideNav />
      <div className="shell">{children}</div>
      <TabBar />
    </WatchProvider>
  );
}
