"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { MonthDatum } from "./types";
import { useHasMounted } from "./use-has-mounted";

const TICK = {
  fill: "var(--ink-faint)",
  fontSize: 10,
  fontFamily: "var(--font-mono)",
};

export function MonthlyBars({
  data,
  height = 160,
}: {
  data: MonthDatum[];
  height?: number;
}) {
  const mounted = useHasMounted();
  return (
    <div
      className="relative w-full tabular-nums"
      style={{ height }}
      role="img"
      aria-label="Monthly generation vs. consumption (kWh)"
    >
      {mounted && (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={data}
          margin={{ top: 12, right: 12, bottom: 4, left: 0 }}
          barCategoryGap={8}
          barGap={2}
        >
          <CartesianGrid
            stroke="var(--rule)"
            strokeDasharray="2 3"
            strokeWidth={0.8}
            vertical={false}
          />
          <XAxis
            dataKey="month"
            tick={TICK}
            stroke="var(--rule)"
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={TICK}
            unit=" kWh"
            tickFormatter={(v) => v.toString()}
            stroke="var(--rule)"
            tickLine={false}
            axisLine={false}
            width={60}
          />
          <Bar dataKey="use" isAnimationActive={false}>
            {data.map((_, i) => (
              <Cell
                key={`use-${i}`}
                fill="var(--rule-strong)"
                fillOpacity={0.18}
              />
            ))}
          </Bar>
          <Bar dataKey="gen" isAnimationActive={false}>
            {data.map((_, i) => (
              <Cell key={`gen-${i}`} fill="var(--accent)" />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      )}
    </div>
  );
}
