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
      <a
        href="#main-content"
        className="sr-only z-[100] focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:rounded-md focus:bg-ink focus:px-4 focus:py-2 focus:text-bg focus:outline-none focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>
      <SunBackdrop />
      <div className="relative z-10 flex min-h-screen flex-col">
        <NavBar />
        <main id="main-content" tabIndex={-1} className="flex-1">
          {children}
        </main>
        <Footer />
      </div>
    </>
  );
}
