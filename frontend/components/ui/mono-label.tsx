import { cn } from "@/lib/utils";

export function MonoLabel({
  children,
  faint = false,
  className,
}: {
  children: React.ReactNode;
  faint?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "font-mono text-[10.5px] uppercase tracking-[0.14em]",
        faint ? "text-ink-faint" : "text-ink-dim",
        className,
      )}
    >
      {children}
    </div>
  );
}
