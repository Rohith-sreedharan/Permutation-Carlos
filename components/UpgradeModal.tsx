import React from 'react';

interface UpgradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTier: string;
  onSelectTier: (tier: string) => void;
}

const TIER_DATA = [
  {
    key: 'starter',
    name: 'Starter',
    sims: '10K',
    price: 'Free',
    features: ['Core visibility', 'Great for casual use', 'Basic game analysis']
  },
  {
    key: 'core',
    name: 'Core',
    sims: '25K',
    price: '$19/mo',
    features: ['Unlock movement tracking', 'Sharper totals and sides', 'Enhanced confidence bands']
  },
  {
    key: 'pro',
    name: 'Pro',
    sims: '50K',
    price: '$39/mo',
    features: ['Full game confidence bands', 'Stronger parlay engine', 'Advanced correlation']
  },
  {
    key: 'elite',
    name: 'Elite',
    sims: '100K',
    price: '$99/mo',
    features: ['Maximum simulation depth', 'Advanced correlation overlays', 'Micro-edge detection'],
    highlight: true
  }
];

const UpgradeModal: React.FC<UpgradeModalProps> = ({ isOpen, onClose, currentTier, onSelectTier }) => {
  if (!isOpen) return null;

  const currentTierIndex = TIER_DATA.findIndex(t => t.key === currentTier);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      ></div>

      {/* Modal */}
      <div className="relative bg-gradient-to-br from-charcoal to-navy rounded-xl border-2 border-gold/30 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-lightGold/70 hover:text-lightGold text-2xl z-10"
        >
          ×
        </button>

        {/* Header */}
        <div className="p-8 border-b border-gold/20">
          <h2 className="text-3xl font-bold text-gold mb-3">
            Unlock Higher Simulation Power
          </h2>
          <p className="text-lightGold/80 leading-relaxed">
            BeatVegas tiers are built around simulation depth. More simulations = tighter projections, 
            cleaner confidence bands, and better edge detection.
          </p>
        </div>

        {/* Tier Grid */}
        <div className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {TIER_DATA.map((tier, index) => {
              const isCurrentTier = tier.key === currentTier;
              const isLowerTier = index <= currentTierIndex;
              const canUpgrade = !isCurrentTier && !isLowerTier;

              return (
                <div
                  key={tier.key}
                  className={`rounded-lg p-5 border-2 transition-all ${
                    tier.highlight
                      ? 'bg-gradient-to-br from-gold/10 to-deepRed/10 border-gold/50'
                      : isCurrentTier
                      ? 'bg-navy/50 border-electric-blue/50'
                      : 'bg-navy/30 border-gold/20'
                  } ${isLowerTier && !isCurrentTier ? 'opacity-50' : ''}`}
                >
                  {/* Tier Header */}
                  <div className="text-center mb-4">
                    <div className={`text-2xl font-bold ${
                      tier.highlight ? 'text-gold' : 'text-lightGold'
                    }`}>
                      {tier.name}
                    </div>
                    <div className="text-sm text-lightGold/70 mb-1">
                      {tier.sims} sims/game
                    </div>
                    <div className={`text-xl font-bold ${
                      tier.highlight ? 'text-gold' : 'text-electric-blue'
                    }`}>
                      {tier.price}
                    </div>
                  </div>

                  {/* Features */}
                  <div className="space-y-2 mb-4">
                    {tier.features.map((feature, idx) => (
                      <div key={idx} className="flex items-start gap-2 text-xs text-lightGold/80">
                        <span className="text-electric-blue mt-0.5">✓</span>
                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>

                  {/* Action Button */}
                  {isCurrentTier ? (
                    <div className="text-center py-2 px-4 bg-electric-blue/20 text-electric-blue rounded font-semibold text-sm">
                      Current Tier
                    </div>
                  ) : isLowerTier ? (
                    <div className="text-center py-2 px-4 bg-navy/50 text-lightGold/40 rounded text-sm">
                      Lower Tier
                    </div>
                  ) : (
                    <button
                      onClick={() => onSelectTier(tier.key)}
                      className={`w-full py-2 px-4 rounded font-bold text-sm transition-all ${
                        tier.highlight
                          ? 'bg-gradient-to-r from-gold to-lightGold text-darkNavy hover:shadow-lg hover:shadow-gold/30'
                          : 'bg-electric-blue/20 text-electric-blue border border-electric-blue/30 hover:bg-electric-blue/30'
                      }`}
                    >
                      Upgrade to {tier.name}
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {/* Additional Info */}
          <div className="mt-6 p-4 bg-navy/30 rounded-lg border border-gold/10">
            <div className="text-xs text-lightGold/70 text-center">
              <strong className="text-lightGold">Note:</strong> Tier upgrades apply immediately. 
              Re-run any game to see it rebuilt with your new simulation power.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UpgradeModal;
