"use client";

export type Tier = "free" | "decision_pack" | "track";

const FEATURES: Record<string, Tier> = {
  "engine.basic_forecast": "free",
  "audit.proposal_extraction": "decision_pack",
  "engine.battery.hourly_dispatch": "decision_pack",
  "engine.scenario.diff": "decision_pack",
  "track.bill_variance": "track",
};

const TIER_RANK: Record<Tier, number> = { free: 0, decision_pack: 1, track: 2 };

export function useEntitlement(featureKey: string, userTier: Tier = "free"): boolean {
  const required = FEATURES[featureKey];
  if (!required) return false;
  return TIER_RANK[userTier] >= TIER_RANK[required];
}
