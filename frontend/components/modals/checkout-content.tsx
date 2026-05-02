import { Btn, Eyebrow, Panel } from "@/components/ui";
import { Currency } from "@/lib/intl";

// Routing-scaffold placeholder. Real Stripe / tier-aware checkout wiring
// is chart-solar-5hq + chart-solar-79i.

const TIERS = [
  { id: "audit", label: "Audit a proposal", price: 79 },
  { id: "founders", label: "Founders pack", price: 129 },
  { id: "track-mo", label: "Track · monthly", price: 9 },
  { id: "track-yr", label: "Track · annual", price: 89 },
] as const;

export function CheckoutContent() {
  return (
    <div className="space-y-5">
      <p className="text-[14px] leading-[1.55] text-ink-2">
        Stripe checkout. Tier-aware — pulls the active product and surfaces a
        sign-in switch for returning customers.
      </p>
      <div className="grid gap-3">
        {TIERS.map((t) => (
          <Panel
            key={t.id}
            className="flex items-center justify-between gap-4"
          >
            <div>
              <Eyebrow color="ink-dim">{t.id}</Eyebrow>
              <p className="text-[15px] text-ink">{t.label}</p>
            </div>
            <Currency value={t.price} />
          </Panel>
        ))}
      </div>
      <Btn kind="accent" type="submit">
        Continue to Stripe
      </Btn>
    </div>
  );
}
