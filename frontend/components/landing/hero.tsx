import { Arrow } from "@/components/icons";
import { BtnLink, Eyebrow } from "@/components/ui";
import { Currency } from "@/lib/intl";
import { AUDIT_PRICE_USD } from "@/lib/pricing";
import { HeroPanel } from "./hero-panel";

// design ref · screen-landing.jsx:Hero (88–125)
export function Hero() {
  return (
    <section className="mx-auto grid max-w-[1360px] grid-cols-1 items-center gap-12 px-10 pt-16 pb-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-16">
      <div>
        <Eyebrow>Plan it · Check it · Track it</Eyebrow>
        <h1 className="m-0 mb-6 text-[clamp(40px,6.2vw,84px)] leading-[1.02] font-display text-balance">
          The honest math
          <br />
          for your roof.
        </h1>
        <p className="m-0 mb-8 max-w-[540px] text-[clamp(16px,1.3vw,19px)] leading-[1.55] text-ink-2">
          Residential solar is sold on 25-year promises built from optimistic
          assumptions. We run the numbers independently — hourly physics,
          Monte Carlo on rate paths, every alternative your capital could be
          doing instead.{" "}
          <em className="text-ink not-italic font-medium">
            No installer affiliations. No lead-gen.
          </em>
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <BtnLink kind="primary" href="/forecast">
            Start free forecast <Arrow />
          </BtnLink>
          <BtnLink kind="ghost" href="/audit">
            Audit my proposal · <Currency value={AUDIT_PRICE_USD} />
          </BtnLink>
          <span className="ml-1 font-mono text-[11px] text-ink-dim">
            no signup to start · address + utility bill
          </span>
        </div>
      </div>
      <HeroPanel />
    </section>
  );
}
