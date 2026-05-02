// Typed data shapes for the chart primitives.
// Each chart accepts a strongly-typed `data` prop so screens stub freely
// against deterministic fixtures during pre-engine UI development.

export type HeroDatum = {
  year: number;
  p10: number;
  p50: number;
  p90: number;
  alt?: number;
};

export type MonthDatum = {
  month: string;
  gen: number;
  use: number;
};

export type BatteryDatum = {
  hour: number;
  solar: number;
  load: number;
  battery: number;
};

export type TornadoItem = {
  name: string;
  low: number;
  high: number;
};
