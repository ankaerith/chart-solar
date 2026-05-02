import { cn } from "@/lib/utils";

type Color = "accent-2" | "accent" | "ink-dim";

const COLOR_TEXT: Record<Color, string> = {
  "accent-2": "text-accent-2",
  accent: "text-accent",
  "ink-dim": "text-ink-dim",
};

const COLOR_BG: Record<Color, string> = {
  "accent-2": "bg-accent-2",
  accent: "bg-accent",
  "ink-dim": "bg-ink-dim",
};

export function Eyebrow({
  children,
  color = "accent-2",
  className,
}: {
  children: React.ReactNode;
  color?: Color;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mb-4 flex items-center gap-[10px] font-mono text-[11px] uppercase tracking-[0.18em]",
        COLOR_TEXT[color],
        className,
      )}
    >
      <span className={cn("inline-block h-px w-6", COLOR_BG[color])} />
      {children}
    </div>
  );
}
