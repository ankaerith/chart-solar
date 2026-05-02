// MathRow — four-column math statement that pins the engine's
// commitments below the modes strip. Each item is a big mono headline
// + a single sentence of context. The whole row sits on `bg-panel-2`
// with the standard `border-y border-rule` band treatment.
//
// Visual contract: design/solar-decisions/project/screen-landing.jsx
// :MathRow (lines 180–206).

const ITEMS = [
  {
    k: "8760",
    l: "hours simulated per year, every year, for 25 years",
  },
  {
    k: "n=500",
    l: "Monte Carlo paths across weather, rates, degradation, hold",
  },
  {
    k: "0%",
    l: "affiliate revenue · lead-gen handoffs · referral fees",
  },
  {
    k: "NEM 3",
    l: "net-billing tariff modeled hourly, post-Apr 2023 CA",
  },
];

export function MathRow() {
  return (
    <section className="border-y border-rule bg-panel-2">
      <div className="mx-auto grid max-w-[1360px] grid-cols-1 gap-8 px-10 py-8 sm:grid-cols-2 lg:grid-cols-4">
        {ITEMS.map((it) => (
          <div
            key={it.k}
            className="flex flex-col gap-1.5 border-l border-rule pl-4"
          >
            <div className="font-display text-[36px] leading-none">
              {it.k}
            </div>
            <div className="text-[12.5px] leading-[1.4] text-ink-dim">
              {it.l}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
