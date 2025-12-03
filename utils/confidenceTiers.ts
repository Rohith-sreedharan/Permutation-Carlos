/**
 * Simulation Stability Index System
 * Measures how stable/consistent simulation results are
 * Indicates data quality tier, not pick quality
 * Consistent across all UI components: badges, gauges, cards, glows
 */

export const STABILITY_TIERS = {
  LOW: { min: 0, max: 49, label: 'Low Stability (Simulation Power Tier)', shortLabel: 'Low Stability', color: '#8B4513', bgColor: '#8B451320', borderColor: '#8B451340', textColor: '#D2691E' },
  MEDIUM: { min: 50, max: 69, label: 'Medium Stability (Simulation Power Tier)', shortLabel: 'Med Stability', color: '#C0C0C0', bgColor: '#C0C0C020', borderColor: '#C0C0C040', textColor: '#E8E8E8' },
  HIGH: { min: 70, max: 100, label: 'High Stability (Simulation Power Tier)', shortLabel: 'High Stability', color: '#D4A64A', bgColor: '#D4A64A20', borderColor: '#D4A64A40', textColor: '#E7C776' }
} as const;

export type StabilityTier = keyof typeof STABILITY_TIERS;

/**
 * Get stability tier from confidence percentage (0-100)
 * Note: Still accepts "confidence" param for backward compatibility
 */
export function getConfidenceTier(confidence: number): typeof STABILITY_TIERS[StabilityTier] {
  if (confidence >= 70) return STABILITY_TIERS.HIGH;
  if (confidence >= 50) return STABILITY_TIERS.MEDIUM;
  return STABILITY_TIERS.LOW;
}

/**
 * Get stability tier name
 */
export function getConfidenceTierName(confidence: number): StabilityTier {
  if (confidence >= 70) return 'HIGH';
  if (confidence >= 50) return 'MEDIUM';
  return 'LOW';
}

/**
 * Get glow effect CSS for tier
 */
export function getConfidenceGlow(confidence: number): string {
  const tier = getConfidenceTier(confidence);
  return `0 0 20px ${tier.color}40, 0 0 40px ${tier.color}20`;
}

/**
 * Get gauge color based on confidence
 */
export function getGaugeColor(confidence: number): string {
  return getConfidenceTier(confidence).color;
}

/**
 * Get badge styling for stability tier
 */
export function getConfidenceBadgeStyle(confidence: number) {
  const tier = getConfidenceTier(confidence);
  return {
    backgroundColor: tier.bgColor,
    borderColor: tier.borderColor,
    color: tier.textColor,
    boxShadow: `0 0 10px ${tier.color}30`
  };
}
