// Single source of truth for product prices in USD. The eventual
// Stripe-driven catalog (chart-solar-79i) keeps these as the
// fallback / static-marketing-copy source while live prices flow
// from the Stripe API on authenticated surfaces.

export const AUDIT_PRICE_USD = 79;
export const TRACK_MONTHLY_USD = 9;
export const DECISION_PACK_PRICE_USD = 79;
