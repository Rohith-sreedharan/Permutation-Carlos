/**
 * Tier Configuration - Simulation Power & Visual Branding
 * Matches backend/config.py SIMULATION_TIERS
 */

export const SIMULATION_TIERS = {
  free: 10000,
  starter: 25000,  // $19.99/mo
  pro: 50000,      // $39.99/mo
  elite: 75000,    // $89/mo
  admin: 100000,   // Internal use
} as const;

export type TierName = keyof typeof SIMULATION_TIERS;

export const TIER_COLORS = {
  free: '#9CA3AF',      // Gray
  starter: '#3B82F6',   // Blue
  pro: '#8B5CF6',       // Purple
  elite: '#F59E0B',     // Amber/Gold
  admin: '#EF4444',     // Red
} as const;

export const TIER_LABELS = {
  free: 'STANDARD',
  starter: 'ENHANCED',
  pro: 'HIGH',
  elite: 'INSTITUTIONAL',
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
