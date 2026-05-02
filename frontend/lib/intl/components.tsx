"use client";

import { cn } from "@/lib/utils";
import {
  formatCurrency,
  formatDate,
  formatKwh,
  formatNumber,
  formatPercent,
} from "./format";
import { type Currency as CurrencyCode, useLocale } from "./locale";

// JSX wrappers — read the active locale via `useLocale()`, format via the
// helpers in `./format`, and render inside a `tabular-nums font-mono` span
// so digits align under the editorial type.
//
// Exposed as plain components (Currency, Num, DateText, Percent, Kwh) so
// call sites stay compact: `<Currency value={31400} />`.

const CLS = "tabular-nums font-mono";

export function Currency({
  value,
  currency,
  options,
  className,
}: {
  value: number;
  currency?: CurrencyCode;
  options?: Intl.NumberFormatOptions;
  className?: string;
}) {
  const locale = useLocale();
  return (
    <span className={cn(CLS, className)}>
      {formatCurrency(value, locale, { ...options, currency })}
    </span>
  );
}

export function Num({
  value,
  options,
  className,
}: {
  value: number;
  options?: Intl.NumberFormatOptions;
  className?: string;
}) {
  const locale = useLocale();
  return (
    <span className={cn(CLS, className)}>
      {formatNumber(value, locale, options)}
    </span>
  );
}

export function Percent({
  value,
  options,
  className,
}: {
  value: number;
  options?: Intl.NumberFormatOptions;
  className?: string;
}) {
  const locale = useLocale();
  return (
    <span className={cn(CLS, className)}>
      {formatPercent(value, locale, options)}
    </span>
  );
}

export function DateText({
  value,
  options,
  className,
}: {
  value: Date | string | number;
  options?: Intl.DateTimeFormatOptions;
  className?: string;
}) {
  const locale = useLocale();
  return (
    <span className={cn(CLS, className)}>
      {formatDate(value, locale, options)}
    </span>
  );
}

export function Kwh({
  value,
  options,
  className,
}: {
  value: number;
  options?: Intl.NumberFormatOptions;
  className?: string;
}) {
  const locale = useLocale();
  return (
    <span className={cn(CLS, className)}>
      {formatKwh(value, locale, options)}
    </span>
  );
}
