import type { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { ResultTier } from "@/lib/api/forecast";

// Three-card next-steps row. The Audit card is the primary action
// (dark ink panel) and gates by audit-credit availability — when the
// user has credits, it deducts; otherwise it routes through checkout.
// The Save card depends on tier (free is locked behind Decision
// Pack). The Track card is a coming-soon waitlist row.
//
// Visual contract: design/solar-decisions/project/screen-results.jsx
// :NextStepsRow + :NextStepRow + :ComingSoonRow (lines 204–294).

function NextStepCard({
  kicker,
  title,
  body,
  cta,
  href,
  primary = false,
  locked = false,
}: {
  kicker: string;
  title: string;
  body: ReactNode;
  cta: string;
  href: string;
  primary?: boolean;
  locked?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex flex-col gap-3 rounded-lg border p-6 transition-transform duration-100 hover:-translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
        primary
          ? "border-ink bg-ink text-bg"
          : "border-rule bg-panel text-ink",
      )}
    >
      <div
        className={cn(
          "font-mono text-[10px] uppercase tracking-[0.14em]",
          primary ? "text-bg/70" : "text-accent-2",
        )}
      >
        {kicker}
      </div>
      <div className="text-[22px] leading-[1.15] font-display">{title}</div>
      <div
        className={cn(
          "flex-1 text-[13px] leading-[1.55]",
          primary ? "text-bg/80" : "text-ink-2",
        )}
      >
        {body}
      </div>
      <div
        className={cn(
          "mt-1 flex items-center justify-between border-t pt-3 text-[13px] font-semibold",
          primary
            ? "border-bg/20 text-bg"
            : locked
              ? "border-rule text-ink-2"
              : "border-rule text-accent",
        )}
      >
        <span>
          {locked && <span aria-hidden="true">🔒 </span>}
          {cta}
        </span>
        <span aria-hidden="true">→</span>
      </div>
    </Link>
  );
}

function ComingSoonCard({
  kicker,
  title,
  body,
  cta,
}: {
  kicker: string;
  title: string;
  body: ReactNode;
  cta: string;
}) {
  return (
    <div className="relative flex flex-col gap-3 rounded-lg border border-dashed border-rule-strong bg-panel-2 p-6 text-ink-2">
      <span className="absolute top-3.5 right-3.5 rounded-md border border-rule-strong px-2 py-[3px] font-mono text-[9px] uppercase tracking-[0.16em] text-ink-2">
        Q3
      </span>
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-dim">
        {kicker}
      </div>
      <div className="text-[22px] leading-[1.15] font-display text-ink-2">
        {title}
      </div>
      <div className="flex-1 text-[13px] leading-[1.55] text-ink-dim">
        {body}
      </div>
      <div className="mt-1 flex items-center justify-between border-t border-dashed border-rule pt-3 text-[13px] font-medium text-ink-dim">
        <span>{cta}</span>
        <span aria-hidden="true">→</span>
      </div>
    </div>
  );
}

export function NextStepsRow({
  tier,
  creditsAudit,
}: {
  tier: ResultTier;
  creditsAudit: number;
}) {
  const auditKicker =
    creditsAudit > 0
      ? `${creditsAudit} audit credit${creditsAudit > 1 ? "s" : ""} available`
      : "check the proposal";
  const auditTitle =
    creditsAudit > 0
      ? "Audit a quote — credit ready"
      : "Audit a quote";
  const auditCta =
    creditsAudit > 0
      ? `Use audit credit (${creditsAudit} left)`
      : "Run an audit";

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <NextStepCard
        kicker={auditKicker}
        title={auditTitle}
        body="Drop your installer's PDF. We diff their year-1 kWh, escalator, dealer fee, and DC:AC ratio against this baseline and produce a one-page variance report + an ask-your-installer question list."
        cta={auditCta}
        href="/audit"
        primary
      />
      <NextStepCard
        kicker="lock these numbers"
        title="Save & methodology PDF"
        body={
          tier === "free"
            ? "Save this forecast and export the methodology PDF — every assumption, every source. Decision Pack required."
            : "Save this forecast (engine + irradiance + tariff hash are pinned). Export the methodology PDF."
        }
        cta={tier === "free" ? "Decision Pack" : "Save & export"}
        href={tier === "free" ? "/checkout" : "/save-forecast"}
        locked={tier === "free"}
      />
      <ComingSoonCard
        kicker="coming soon"
        title="Track post-install"
        body="Compare monthly bills and inverter data against this forecast once your system is live. Get notified when we open the waitlist."
        cta="Notify me"
      />
    </div>
  );
}
