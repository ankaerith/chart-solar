import { cn } from "@/lib/utils";

// Brand: "Chart Solar" (the design ref ships the same radiating-sun mark
// under the design-tool name "Solar Decisions" — the visual is identical,
// only the wordmark text differs to match the actual product brand).

export function Wordmark({
  size = 22,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <div
      className={cn("inline-flex items-center gap-[10px] text-ink", className)}
    >
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="4.2" fill="var(--accent)" />
        <g
          stroke="var(--accent)"
          strokeWidth="1.6"
          strokeLinecap="round"
        >
          <line x1="12" y1="1.5" x2="12" y2="4.5" />
          <line x1="12" y1="19.5" x2="12" y2="22.5" />
          <line x1="1.5" y1="12" x2="4.5" y2="12" />
          <line x1="19.5" y1="12" x2="22.5" y2="12" />
          <line x1="4.4" y1="4.4" x2="6.5" y2="6.5" />
          <line x1="17.5" y1="17.5" x2="19.6" y2="19.6" />
          <line x1="4.4" y1="19.6" x2="6.5" y2="17.5" />
          <line x1="17.5" y1="6.5" x2="19.6" y2="4.4" />
        </g>
      </svg>
      <span
        className="font-display tracking-[var(--display-tracking)] text-[18px] font-[var(--display-weight)]"
      >
        Chart Solar
      </span>
    </div>
  );
}
