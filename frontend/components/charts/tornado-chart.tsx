"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { TornadoItem } from "./types";
import { useHasMounted } from "./use-has-mounted";

const AXIS = {
  fill: "var(--ink-faint)",
  fontSize: 10,
  fontFamily: "var(--font-mono)",
};

const NAME_TICK = {
  fill: "var(--ink-2)",
  fontSize: 11.5,
  fontFamily: "var(--font-sans)",
};

function formatK(v: number) {
  const abs = Math.abs(v);
  return `${v < 0 ? "−" : ""}${(abs / 1000).toFixed(0)}k`;
}

export function TornadoChart({
  items,
  height = 240,
}: {
  items: TornadoItem[];
  height?: number;
}) {
  // Sort by impact magnitude — biggest swing on top.
  const sorted = [...items]
    .map((it) => ({ ...it, span: Math.abs(it.high - it.low) }))
    .sort((a, b) => b.span - a.span)
    .map(({ name, low, high }) => ({
      name,
      // Recharts range bar: dataKey returning [start, end] per row.
      range: [low, high] as [number, number],
      low,
      high,
    }));

  const max = Math.max(
    ...sorted.flatMap((it) => [Math.abs(it.low), Math.abs(it.high)]),
  );

  const mounted = useHasMounted();
  return (
    <div
      className="relative w-full tabular-nums"
      style={{ height }}
      role="img"
      aria-label="Sensitivity (tornado) chart — net-present-value swing per input, sorted by magnitude"
    >
      {mounted && (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={sorted}
          layout="vertical"
          margin={{ top: 8, right: 60, bottom: 8, left: 8 }}
        >
          <CartesianGrid stroke="var(--rule)" strokeWidth={0.6} horizontal={false} />
          <XAxis
            type="number"
            domain={[-max * 1.1, max * 1.1]}
            tick={AXIS}
            tickFormatter={formatK}
            stroke="var(--rule)"
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={NAME_TICK}
            stroke="var(--rule)"
            tickLine={false}
            axisLine={false}
            width={200}
          />
          <ReferenceLine x={0} stroke="var(--rule-strong)" strokeWidth={1} />
          <Bar dataKey="range" isAnimationActive={false} barSize={18}>
            {sorted.map((_, i) => (
              <Cell key={`tor-${i}`} fill="var(--accent)" fillOpacity={0.85} />
            ))}
            <LabelList
              dataKey="low"
              position="left"
              formatter={(v: unknown) =>
                typeof v === "number" ? formatK(v) : ""
              }
              style={{
                fontSize: 9.5,
                fontFamily: "var(--font-mono)",
                fill: "var(--ink-dim)",
              }}
            />
            <LabelList
              dataKey="high"
              position="right"
              formatter={(v: unknown) =>
                typeof v === "number" ? formatK(v) : ""
              }
              style={{
                fontSize: 9.5,
                fontFamily: "var(--font-mono)",
                fill: "var(--ink-dim)",
              }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      )}
    </div>
  );
}
