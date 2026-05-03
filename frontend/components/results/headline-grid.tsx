import { MonoLabel } from "@/components/ui";
import { Currency, Num } from "@/lib/intl";
import { cn } from "@/lib/utils";
import type { ForecastResultMock } from "@/lib/api/forecast";

// design ref · screen-results.jsx:HeadlineGrid (40–75)

type Tile = {
  kicker: string;
  value: React.ReactNode;
  sub: string;
  accent?: boolean;
  tight?: boolean;
};

function buildTiles(headline: ForecastResultMock["headline"]): Tile[] {
  return [
    {
      kicker: "Median NPV",
      value: <Currency value={headline.nplv50} />,
      sub: "discount 5.5% · n=500",
      accent: true,
    },
    {
      kicker: "Disc. payback",
      value: <span>{headline.paybackYears.toFixed(1)} yr</span>,
      sub: "vs installer 7 yr",
    },
    {
      kicker: "Crossover",
      value: <span>yr {headline.crossoverYear}</span>,
      sub: "$/kWh < utility",
    },
    {
      kicker: "IRR (median)",
      value: <span>{headline.irrPct.toFixed(1)}%</span>,
      sub: "reinvest. caveat",
    },
    {
      kicker: "Lifetime tCO₂",
      value: <Num value={headline.lifetimeTonsCO2} />,
      sub: "WECC marginal",
    },
    {
      kicker: "P10 → P90",
      value: (
        <span>
          <Currency
            value={headline.nplv10}
            options={{
              notation: "compact",
              maximumFractionDigits: 1,
            }}
          />
          –
          <Currency
            value={headline.nplv90}
            options={{
              notation: "compact",
              maximumFractionDigits: 1,
            }}
          />
        </span>
      ),
      sub: "80% of paths",
      tight: true,
    },
  ];
}

export function HeadlineGrid({
  headline,
}: {
  headline: ForecastResultMock["headline"];
}) {
  const tiles = buildTiles(headline);
  return (
    <div className="grid grid-cols-2 border-y border-rule sm:grid-cols-3 lg:grid-cols-6">
      {tiles.map((tile, i) => (
        <div
          key={tile.kicker}
          className={cn(
            "min-w-0 bg-bg px-[18px] py-5",
            i < tiles.length - 1 && "border-r border-rule",
          )}
        >
          <MonoLabel>{tile.kicker}</MonoLabel>
          <div
            className={cn(
              "mt-1.5 truncate font-display leading-[1.1] tabular-nums",
              tile.tight ? "text-[22px]" : "text-[28px]",
              tile.accent ? "text-accent" : "text-ink",
            )}
          >
            {tile.value}
          </div>
          <div className="mt-1 truncate font-mono text-[11px] text-ink-dim">
            {tile.sub}
          </div>
        </div>
      ))}
    </div>
  );
}
