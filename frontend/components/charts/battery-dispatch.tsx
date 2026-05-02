"use client";

import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { BatteryDatum } from "./types";
import { useHasMounted } from "./use-has-mounted";

const TICK = {
  fill: "var(--ink-faint)",
  fontSize: 10,
  fontFamily: "var(--font-mono)",
};

export function BatteryDispatch({
  data,
  onPeak = [16, 21],
  height = 220,
}: {
  data: BatteryDatum[];
  onPeak?: [number, number];
  height?: number;
}) {
  const mounted = useHasMounted();
  return (
    <div
      className="relative w-full tabular-nums"
      style={{ height }}
      role="img"
      aria-label="Twenty-four-hour battery dispatch — solar generation, household load, charge / discharge bars, on-peak window highlighted"
    >
      {mounted && (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={data}
          margin={{ top: 14, right: 60, bottom: 4, left: 0 }}
        >
          <defs>
            <linearGradient id="bd-solar" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.18} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--rule)" strokeWidth={0.6} vertical={false} />
          <XAxis
            dataKey="hour"
            type="number"
            domain={[0, 23]}
            ticks={[0, 6, 12, 18, 23]}
            tickFormatter={(v) => `${String(v).padStart(2, "0")}:00`}
            tick={TICK}
            stroke="var(--rule)"
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={TICK}
            unit=" kW"
            tickFormatter={(v) => v.toString()}
            stroke="var(--rule)"
            tickLine={false}
            axisLine={false}
            width={50}
          />
          <ReferenceArea
            x1={onPeak[0]}
            x2={onPeak[1]}
            fill="var(--accent-2)"
            fillOpacity={0.06}
            label={{
              value: "ON-PEAK",
              position: "insideTop",
              fontSize: 9,
              fontFamily: "var(--font-mono)",
              fill: "var(--accent-2)",
              letterSpacing: "0.1em",
            }}
          />
          <ReferenceLine y={0} stroke="var(--rule-strong)" strokeWidth={0.8} />
          <Area
            type="monotone"
            dataKey="solar"
            stroke="var(--accent)"
            strokeWidth={1.6}
            fill="url(#bd-solar)"
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="load"
            stroke="var(--ink)"
            strokeWidth={1.4}
            strokeDasharray="3 3"
            dot={false}
            isAnimationActive={false}
          />
          <Bar dataKey="battery" isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell
                key={`bat-${i}`}
                fill={d.battery >= 0 ? "var(--good)" : "var(--accent-2)"}
                fillOpacity={0.7}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
      )}
    </div>
  );
}
