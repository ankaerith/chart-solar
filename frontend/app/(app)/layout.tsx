import type { ReactNode } from "react";
import { SunBackdrop } from "@/components/layout";

// Product-flow layout: each child renders its own chrome (wizard nav,
// audit progress bar). Marketing's NavBar is intentionally absent.

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <a
        href="#main-content"
        className="sr-only z-[100] focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:rounded-md focus:bg-ink focus:px-4 focus:py-2 focus:text-bg focus:outline-none focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>
      <SunBackdrop />
      <main id="main-content" tabIndex={-1} className="relative z-10">
        {children}
      </main>
    </>
  );
}
