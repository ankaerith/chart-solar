import type { ReactNode } from "react";
import { Footer, NavBar, SunBackdrop } from "@/components/layout";

// Marketing route group: SEO surfaces (`/`, `/pricing`, `/methodology`,
// `/notes/*`). Server-rendered, prerendered. Carries the editorial
// chrome — sticky NavBar, Footer, and the fixed SunBackdrop motif.

export default function MarketingLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <>
      <SunBackdrop />
      <div className="relative z-10 flex min-h-screen flex-col">
        <NavBar />
        <main className="flex-1">{children}</main>
        <Footer />
      </div>
    </>
  );
}
