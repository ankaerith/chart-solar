"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { HeroDatum } from "./types";
import { useHasMounted } from "./use-has-mounted";

const TICK = {
  fill: "var(--ink-faint)",
  fontSize: 10,
  fontFamily: "var(--font-mono)",
};

function formatDollarsK(v: number) {
  const abs = Math.abs(v);
  return `${v < 0 ? "−" : ""}$${(abs / 1000).toFixed(0)}k`;
}

export function HeroChart({
  data,
  height = 360,
  showAlt = true,
}: {
  data: HeroDatum[];
  height?: number;
  showAlt?: boolean;
}) {
  // Recharts Area with `dataKey` returning [low, high] renders a range band.
  // We synthesise it by mapping each datum to a tuple range [p10, p90].
  const mounted = useHasMounted();
  const ranged = data.map((d) => ({
    ...d,
    band: [d.p10, d.p90] as [number, number],
  }));

  return (
    <div
      className="relative w-full tabular-nums"
      style={{ height }}
      role="img"
      aria-label="Cumulative net wealth — solar vs. high-yield-savings opportunity cost — Monte Carlo P10–P90 fan with median"
    >
      {mounted && (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={ranged}
          margin={{ top: 18, right: 24, bottom: 8, left: 8 }}
        >
          <defs>
            <linearGradient id="hero-fan" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.28} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--rule)" strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="year"
            ticks={[0, 5, 10, 15, 20, 25]}
            tick={TICK}
            tickFormatter={(v) => `y${v}`}
            stroke="var(--rule)"
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={TICK}
            tickFormatter={formatDollarsK}
            stroke="var(--rule)"
            tickLine={false}
            axisLine={false}
            width={56}
          />
          <ReferenceLine
            y={0}
            stroke="var(--rule-strong)"
            strokeDasharray="3 3"
            strokeOpacity={0.6}
          />
          <Area
            type="monotone"
            dataKey="band"
            fill="url(#hero-fan)"
            stroke="none"
            isAnimationActive={false}
          />
          {showAlt && (
            <Line
              type="monotone"
              dataKey="alt"
              stroke="var(--ink-dim)"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              isAnimationActive={false}
            />
          )}
          <Line
            type="monotone"
            dataKey="p50"
            stroke="var(--accent)"
            strokeWidth={2.25}
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
      )}
    </div>
  );
}
