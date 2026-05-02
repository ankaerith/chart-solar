import { Eyebrow, Footnote, Panel } from "@/components/ui";

// Routing-scaffold placeholder. The dev-mode "click the link" affordance
// from solar-decisions/project/auth.jsx:123 lands when the magic-link
// flow is wired (chart-solar-bcy / chart-solar-bcy.2).

export function MagicSentContent() {
  return (
    <div className="space-y-5">
      <p className="text-[14px] leading-[1.55] text-ink-2">
        Check your inbox. We just sent a one-tap link — open it on this
        device and we&apos;ll bring you back to where you left off.
      </p>
      <Panel className="space-y-2">
        <Eyebrow color="ink-dim">Dev affordance</Eyebrow>
        <p className="font-mono text-[12px] text-ink-dim">
          The link will surface here in dev mode (chart-solar-bcy.2).
        </p>
      </Panel>
      <Footnote n={1}>
        Magic-link expiry is 15 minutes. Re-request from the sign-in screen
        if it lapses.
      </Footnote>
    </div>
  );
}
