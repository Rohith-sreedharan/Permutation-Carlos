export interface TierConfig {
  key: string;
  label: string;
  sims: number;
  color: string;
  index: number;
  // Numerical Accuracy additions (per spec Section 5.1)
  stability_band: number;  // ±% variance band
  confidence_multiplier: number;  // Weight for confidence calculation
  min_edge_required: number;  // Minimum edge to classify as EDGE
  description: string;
}

export const TIERS: Record<string, TierConfig> = {
  starter: { 
    key: 'starter', 
    label: "Starter", 
    sims: 10000, 
    color: "text-gray-400", 
    index: 0,
    stability_band: 0.15,  // ±15%
    confidence_multiplier: 0.7,
    min_edge_required: 0.05,
    description: "Entry-level analysis with wider confidence bands"
  },
  core: { 
    key: 'core', 
    label: "Core", 
    sims: 25000, 
    color: "text-blue-400", 
    index: 1,
    stability_band: 0.10,  // ±10%
    confidence_multiplier: 0.85,
    min_edge_required: 0.04,
    description: "Standard depth for most scenarios"
  },
  pro: { 
    key: 'pro', 
    label: "Pro", 
    sims: 50000, 
    color: "text-purple-400", 
    index: 2,
    stability_band: 0.06,  // ±6%
    confidence_multiplier: 0.95,
    min_edge_required: 0.03,
    description: "High-resolution projections"
  },
  elite: { 
    key: 'elite', 
    label: "Elite", 
    sims: 100000, 
    color: "text-gold", 
    index: 3,
    stability_band: 0.035,  // ±3.5%
    confidence_multiplier: 1.0,
    min_edge_required: 0.03,
    description: "Maximum precision Monte Carlo"
  },
  founder: { 
    key: 'founder', 
    label: "Founder", 
    sims: 100000, 
    color: "text-gold", 
    index: 3,
    stability_band: 0.035,  // ±3.5%
    confidence_multiplier: 1.0,
    min_edge_required: 0.03,
    description: "VIP tier with Elite power"
  }
};

export const MAX_SIMS = 100000;

export const getTierConfig = (tierKey: string): TierConfig => {
  return TIERS[tierKey.toLowerCase()] || TIERS.starter;
};

export const getNextTier = (currentTier: string): TierConfig | null => {
  const current = getTierConfig(currentTier);
  const tierKeys = Object.keys(TIERS).filter(k => k !== 'founder'); // Exclude founder from upgrade path
  const currentIndex = tierKeys.findIndex(k => TIERS[k].index === current.index);
  
  if (currentIndex === -1 || currentIndex >= tierKeys.length - 1) return null;
  
  return TIERS[tierKeys[currentIndex + 1]];
};

export const getSimPowerMessage = (tierKey: string, context: 'game' | 'confidence' | 'parlay'): string => {
  const tier = getTierConfig(tierKey);
  const nextTier = getNextTier(tierKey);
  
  if (tier.sims >= MAX_SIMS) {
    if (context === 'game') {
      return `Monte Carlo Simulation (${tier.sims.toLocaleString()} iterations – ${tier.label} max)\nRunning at full BeatVegas simulation depth.`;
    } else if (context === 'confidence') {
      return `${tier.sims.toLocaleString()} sims active – maximum resolution.`;
    } else {
      return `${tier.label} sim power (${(tier.sims / 1000).toFixed(0)}K) – full BeatVegas grid unlocked.`;
    }
  }

  if (context === 'game') {
    return `Monte Carlo Simulation (${tier.sims.toLocaleString()} iterations – ${tier.label} cap)\nHigher tiers re-run this matchup at ${nextTier ? nextTier.sims.toLocaleString() : MAX_SIMS.toLocaleString()} sims for tighter edges.`;
  } else if (context === 'confidence') {
    return `${tier.sims.toLocaleString()} sims active. ${nextTier ? nextTier.label : 'Elite'} tier${nextTier ? 's' : ''} use ${nextTier ? nextTier.sims.toLocaleString() : MAX_SIMS.toLocaleString()} sims on this matchup.`;
  } else {
    return `This parlay is built on ${(tier.sims / 1000).toFixed(0)}K simulations. ${nextTier ? nextTier.label : 'Elite'} tier${nextTier ? 's' : ''} deepen${nextTier ? '' : 's'} the sim grid to ${nextTier ? (nextTier.sims / 1000).toFixed(0) : '100'}K sims.`;
  }
};

export const shouldShowUpgradePrompt = (
  tierKey: string,
  context: {
    volatility?: string;
    legCount?: number;
    feature?: string;
  }
): { show: boolean; message: string; requiredTier?: string } => {
  const tier = getTierConfig(tierKey);
  const nextTier = getNextTier(tierKey);
  
  if (!nextTier) {
    return { show: false, message: '' };
  }

  // High volatility games
  if (context.volatility === 'HIGH' && tier.sims < 50000) {
    return {
      show: true,
      message: `High-variance matchup detected. More simulation power can reduce noise in spots like this.`,
      requiredTier: tier.sims < 25000 ? 'core' : 'pro'
    };
  }

  // Multi-leg parlays
  if (context.legCount && context.legCount >= 3 && tier.sims < 50000) {
    return {
      show: true,
      message: `Multi-leg parlays benefit most from higher Simulation Power. ${nextTier.label} Tier re-runs this parlay at ${(nextTier.sims / 1000).toFixed(0)}K sims with improved correlation handling.`,
      requiredTier: nextTier.key
    };
  }

  // Feature gates
  if (context.feature) {
    const featureGates: Record<string, { minSims: number; tierKey: string; message: string }> = {
      movement: {
        minSims: 25000,
        tierKey: 'core',
        message: 'Core Tier unlocks live line movement + model vs market tracking built on 25K simulations each game.'
      },
      confidence_bands: {
        minSims: 50000,
        tierKey: 'pro',
        message: 'Pro Tier unlocks deeper confidence bands and higher-resolution margins of victory (50K sims).'
      },
      advanced_correlation: {
        minSims: 100000,
        tierKey: 'elite',
        message: 'Elite re-runs this matchup at 100K simulations with full correlation overlays and micro-edge detection.'
      }
    };

    const gate = featureGates[context.feature];
    if (gate && tier.sims < gate.minSims) {
      return {
        show: true,
        message: gate.message,
        requiredTier: gate.tierKey
      };
    }
  }

  return { show: false, message: '' };
};
