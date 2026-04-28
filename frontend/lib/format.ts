export function formatCurrency(value: number, currency: "USD" | "GBP" = "USD"): string {
  return new Intl.NumberFormat(currency === "GBP" ? "en-GB" : "en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatKwh(value: number): string {
  return `${value.toLocaleString()} kWh`;
}

export function formatPercent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}
