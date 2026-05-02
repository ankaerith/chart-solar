import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Footnote({
  n,
  children,
  className,
}: {
  n: number | string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative pl-[18px] font-sans text-[12px] leading-[1.5] text-ink-dim",
        className,
      )}
    >
      <sup className="absolute top-0 left-0 font-mono text-accent-2">{n}</sup>
      {children}
    </div>
  );
}
