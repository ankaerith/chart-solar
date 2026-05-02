import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { MonoLabel } from "./mono-label";

export function Field({
  label,
  hint,
  footnote,
  children,
  className,
}: {
  label: string;
  hint?: ReactNode;
  footnote?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-baseline justify-between">
        <MonoLabel>{label}</MonoLabel>
        {hint && (
          <span className="font-mono text-[11px] text-ink-faint">{hint}</span>
        )}
      </div>
      {children}
      {footnote && (
        <div className="text-[12px] leading-[1.4] text-ink-dim italic">
          {footnote}
        </div>
      )}
    </label>
  );
}
