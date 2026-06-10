/**
 * Tier Configuration - Simulation Power & Visual Branding
 * Matches backend/config.py SIMULATION_TIERS
 *
 * LOCKED MAPPING (Phase 2 Day 1 — operator approved):
 *   Intelligence Preview  →  free tier    →  10,000  Intelligence Cycles
 *   BeatVegas Platform    →  elite tier   →  100,000 Intelligence Cycles
 *   Telegram Syndicate    →  free tier    →  no Decision Engine access
 *
 * Stripe plan IDs → internal tier: see PLAN_TIER_MAP below.
 * Any Stripe webhook assigning a subscription MUST write one of the
 * TierName values into the user's tier field in MongoDB.
 */

export const SIMULATION_TIERS = {
  free: 10000,
  starter: 25000,
  core: 35000,
  pro: 50000,
  elite: 100000,   // BeatVegas Platform ($97/mo) — 100K Intelligence Cycles
  sharps_room: 100000,
  founder: 100000,
  admin: 100000,   // Internal use
} as const;

export type TierName = keyof typeof SIMULATION_TIERS;

/**
 * Stripe plan ID → internal tier name.
 * Source of truth for Phase 2 Stripe webhook handler.
 * Platform subscribers MUST be assigned "elite" so they receive 100K cycles.
 */
export const PLAN_TIER_MAP: Record<string, TierName> = {
  beatvegas_platform: 'elite',   // $97/mo — 100,000 Intelligence Cycles
  telegram_syndicate: 'free',    // $39/mo — no Decision Engine cycles
} as const;

export const TIER_COLORS = {
  free: '#9CA3AF',        // Gray — Intelligence Preview
  starter: '#3B82F6',     // Blue
  core: '#06B6D4',        // Cyan
  pro: '#8B5CF6',         // Purple
  elite: '#F59E0B',       // Amber/Gold — BeatVegas Platform
  sharps_room: '#F59E0B', // Amber/Gold
  founder: '#EF4444',     // Red
  admin: '#EF4444',       // Red
} as const;

export const TIER_LABELS = {
  free: 'STANDARD',
  starter: 'ENHANCED',
  core: 'ENHANCED',
  pro: 'HIGH',
  elite: 'INSTITUTIONAL',
  sharps_room: 'INSTITUTIONAL',
  founder: 'INSTITUTIONAL',
  admin: 'HOUSE_EDGE',
} as const;

export const TIER_PRICES = {
  free: 'Free',
  starter: '$19.99/mo',
  pro: '$39.99/mo',
  elite: '$89/mo',
  admin: 'Internal',
} as const;

/**
 * Get simulation count with formatting
 */
export function formatSimulationCount(count: number): string {
  if (count >= 1000) {
    return `${(count / 1000).toFixed(0)}K`;
  }
  return count.toString();
}

/**
 * Get tier info from user object
 */
export function getUserTierInfo(user: any) {
  const tier = (user?.subscription_tier || 'free') as TierName;
  return {
    tier,
    simulations: SIMULATION_TIERS[tier],
    color: TIER_COLORS[tier],
    label: TIER_LABELS[tier],
    price: TIER_PRICES[tier],
  };
}
