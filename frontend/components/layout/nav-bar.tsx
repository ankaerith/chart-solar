"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Arrow, Wordmark } from "@/components/icons";
import { BtnLink } from "@/components/ui/btn";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/forecast", label: "Forecast", match: ["/forecast", "/results"] },
  { href: "/audit", label: "Audit", match: ["/audit"] },
  { href: "/pricing", label: "Pricing", match: ["/pricing"] },
  { href: "/methodology", label: "How it works", match: ["/methodology"] },
  { href: "/notes", label: "Field Notes", match: ["/notes"] },
] as const;

function isActive(pathname: string, match: ReadonlyArray<string>) {
  return match.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function NavBar() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-50 flex flex-wrap items-center justify-between gap-4 border-b border-rule bg-bg px-10 py-[18px]">
      <Link
        href="/"
        aria-label="Chart Solar — home"
        className="rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
      >
        <Wordmark />
      </Link>

      <div className="flex items-center gap-7">
        {TABS.map((t) => {
          const active = isActive(pathname, t.match);
          return (
            <Link
              key={t.href}
              href={t.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "border-b-[1.5px] py-[6px] text-[13.5px] tracking-[0.01em] transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "border-ink font-semibold text-ink"
                  : "border-transparent font-medium text-ink-2",
              )}
            >
              {t.label}
            </Link>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <Link
          href="/signin"
          className="rounded-md px-3 py-2 text-[13.5px] font-medium text-ink-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Sign in
        </Link>
        <BtnLink kind="accent" href="/forecast">
          Run my forecast <Arrow />
        </BtnLink>
      </div>
    </nav>
  );
}
