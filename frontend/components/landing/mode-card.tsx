import type { ReactNode } from "react";
import Link from "next/link";
import { MonoLabel } from "@/components/ui";
import { cn } from "@/lib/utils";

// ModeCard — one of three cards in the modes strip. Editorial card
// with kicker + tag pill, display headline (accent on the primary
// card), body, and a footer line of mono provenance text + ↓ glyph.
//
// Visual contract: design/solar-decisions/project/screen-landing.jsx
// :ModeCard (lines 127–156).

export function ModeCard({
  index,
  name,
  tag,
  head,
  body,
  footer,
  href,
  primary = false,
}: {
  index: string;
  name: string;
  tag: ReactNode;
  head: string;
  body: ReactNode;
  footer: string;
  href: string;
  primary?: boolean;
}) {
  return (
    <Link
      href={href}
      className="flex flex-col gap-4 rounded-lg border border-rule bg-panel p-7 transition-transform duration-100 hover:-translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
    >
      <div className="flex items-baseline justify-between gap-3">
        <MonoLabel>
          {index} · {name}
        </MonoLabel>
        <span className="rounded-md border border-rule px-1.5 py-[2px] font-mono text-[10px] text-ink-dim">
          {tag}
        </span>
      </div>
      <h3
        className={cn(
          "m-0 text-[26px] leading-[1.1] font-display",
          primary ? "text-accent" : "text-ink",
        )}
      >
        {head}
      </h3>
      <p className="m-0 flex-1 text-[14px] leading-[1.55] text-ink-2">
        {body}
      </p>
      <div className="flex items-center justify-between border-t border-rule pt-3.5 font-mono text-[11px] text-ink-dim">
        <span>{footer}</span>
        <span className="text-accent" aria-hidden="true">
          →
        </span>
      </div>
    </Link>
  );
}
