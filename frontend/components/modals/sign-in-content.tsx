// Shared body for /signin in both forms:
//   • Modal overlay      — app/(marketing)/@modal/(.)signin/page.tsx
//   • Full-page fallback — app/(marketing)/signin/page.tsx
//
// The bead (chart-solar-2hf.1) is the routing scaffolding only —
// real magic-link wiring lives in the auth epic (chart-solar-bcy and
// children). This component is a placeholder shell with the intended
// shape so the auth bead can drop in the real form without touching
// the route surface.

import { Btn, Eyebrow, Field, TextInput } from "@/components/ui";

export function SignInContent() {
  return (
    <div className="space-y-5">
      <p className="text-[14px] leading-[1.55] text-ink-2">
        Magic-link sign-in. We send a one-tap link to your inbox — no
        password to forget, no support burden.
      </p>
      <Field label="Email" footnote="We never sell or share your email.">
        <TextInput placeholder="alice@example.com" type="email" />
      </Field>
      <div className="flex items-center gap-3">
        <Btn kind="primary" type="submit">
          Send magic link
        </Btn>
        <span className="font-mono text-[11px] text-ink-faint">
          Wired up in chart-solar-bcy
        </span>
      </div>
      <Eyebrow color="ink-dim">Why magic-link only</Eyebrow>
      <p className="text-[13px] leading-[1.55] text-ink-dim">
        One-time + occasional usage pattern. Password becomes optional in
        Account once Track subscribers ask for it.
      </p>
    </div>
  );
}
