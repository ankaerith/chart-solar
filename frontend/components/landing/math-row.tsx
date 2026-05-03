// design ref · screen-landing.jsx:MathRow (180–206)

const ITEMS = [
  {
    figure: "8760",
    caption: "hours simulated per year, every year, for 25 years",
  },
  {
    figure: "n=500",
    caption: "Monte Carlo paths across weather, rates, degradation, hold",
  },
  {
    figure: "0%",
    caption: "affiliate revenue · lead-gen handoffs · referral fees",
  },
  {
    figure: "NEM 3",
    caption: "net-billing tariff modeled hourly, post-Apr 2023 CA",
  },
];

export function MathRow() {
  return (
    <section className="border-y border-rule bg-panel-2">
      <div className="mx-auto grid max-w-[1360px] grid-cols-1 gap-8 px-10 py-8 sm:grid-cols-2 lg:grid-cols-4">
        {ITEMS.map((it) => (
          <div
            key={it.figure}
            className="flex flex-col gap-1.5 border-l border-rule pl-4"
          >
            <div className="font-display text-[36px] leading-none">
              {it.figure}
            </div>
            <div className="text-[12.5px] leading-[1.4] text-ink-dim">
              {it.caption}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
