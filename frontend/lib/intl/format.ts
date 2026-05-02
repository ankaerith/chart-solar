// Locale-aware string formatters built on Intl.*. All numerics should flow
// through these helpers so that switching the active locale flips currency
// symbols, decimal separators, and date order in one place.
//
// Pair with the JSX wrappers in `./components` (Currency, Num, Date, …)
// when rendering inline — those wrappers add the `tabular-nums font-mono`
// classes so digits align under the editorial type.

import {
  CURRENCY_FOR_LOCALE,
  type Currency,
  type Locale,
} from "./locale";

export function formatCurrency(
  value: number,
  locale: Locale,
  options: Intl.NumberFormatOptions & { currency?: Currency } = {},
): string {
  const { currency = CURRENCY_FOR_LOCALE[locale], ...rest } = options;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
    ...rest,
  }).format(value);
}

export function formatNumber(
  value: number,
  locale: Locale,
  options: Intl.NumberFormatOptions = {},
): string {
  return new Intl.NumberFormat(locale, options).format(value);
}

export function formatPercent(
  value: number,
  locale: Locale,
  options: Intl.NumberFormatOptions = {},
): string {
  // Caller passes the fractional value (0.145 → 14.5%). Default to 1 d.p.;
  // the engine often emits values like 0.0345 where 1 d.p. reads cleanly.
  return new Intl.NumberFormat(locale, {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
    ...options,
  }).format(value);
}

export function formatDate(
  value: Date | string | number,
  locale: Locale,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium" },
): string {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat(locale, options).format(date);
}

export function formatKwh(
  value: number,
  locale: Locale,
  options: Intl.NumberFormatOptions = {},
): string {
  // kWh is locale-stable as a unit symbol; only the digit grouping varies.
  const n = formatNumber(value, locale, options);
  return `${n} kWh`;
}
