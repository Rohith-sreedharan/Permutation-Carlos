import React from 'react';

interface FeatureGateProps {
  feature: 'movement' | 'confidence_bands' | 'advanced_correlation';
  requiredTier: string;
  requiredSims: number;
  onUpgradeClick?: () => void;
}

const FEATURE_DETAILS = {
  movement: {
    title: 'Line Movement Tracking',
    description: 'Core Tier unlocks live line movement + model vs market tracking built on 25K simulations each game.',
    icon: '📊'
  },
  confidence_bands: {
    title: 'Advanced Confidence Bands',
    description: 'Pro Tier unlocks deeper confidence bands (95% & 99.7%) and higher-resolution margins of victory (50K sims).',
    icon: '📈'
  },
  advanced_correlation: {
    title: 'Elite Simulation Lab',
    description: 'Elite re-runs this matchup at 100K simulations with full correlation overlays and micro-edge detection.',
    icon: '🔬'
  }
};

const FeatureGate: React.FC<FeatureGateProps> = ({
  feature,
  requiredTier,
  requiredSims,
  onUpgradeClick
}) => {
  const details = FEATURE_DETAILS[feature];

  return (
    <div className="bg-gradient-to-br from-charcoal/80 to-navy/80 backdrop-blur-sm rounded-lg border-2 border-gold/30 p-8 text-center">
      <div className="text-5xl mb-4">{details.icon}</div>
      <div className="text-3xl mb-2">🔒</div>
      <h3 className="text-xl font-bold text-gold mb-3">
        Requires {requiredTier.charAt(0).toUpperCase() + requiredTier.slice(1)} Simulation Power
      </h3>
      <div className="text-sm text-lightGold/80 mb-1">
        ({requiredSims.toLocaleString()} sims/game)
      </div>
      <p className="text-sm text-lightGold/70 mb-6 max-w-md mx-auto">
        {details.description}
      </p>
      {onUpgradeClick && (
        <button
          onClick={onUpgradeClick}
          className="px-6 py-3 bg-gradient-to-r from-gold to-lightGold text-darkNavy font-bold rounded-lg hover:shadow-xl hover:shadow-gold/30 transition-all transform hover:scale-105"
        >
          Upgrade to {requiredTier.charAt(0).toUpperCase() + requiredTier.slice(1)}
        </button>
      )}
      <div className="mt-4 text-xs text-lightGold/50">
        Higher tiers unlock deeper analysis with more simulation power
      </div>
    </div>
  );
};

export default FeatureGate;
