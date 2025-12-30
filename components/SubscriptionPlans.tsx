import React from 'react';

export interface SubscriptionTier {
  name: string;
  price: number;
  simulations: number;
  maxPicksPerDay: number;
  features: string[];
  popular?: boolean;
  limited?: boolean;
}

export const SUBSCRIPTION_TIERS: SubscriptionTier[] = [
  {
    name: 'Starter',
    price: 29.99,
    simulations: 10000,
    maxPicksPerDay: 5,
    features: [
      '5 AI picks per day',
      '10K iteration Monte Carlo sims',
      'Basic win probability analysis',
      'Community access (0.5x weight)'
    ]
  },
  {
    name: 'Pro',
    price: 49.99,
    simulations: 50000,
    maxPicksPerDay: 15,
    popular: true,
    features: [
      '15 AI picks per day',
      '50K iteration Monte Carlo sims',
      'CLV tracking & analysis',
      'Prop mispricing alerts',
      'Parlay correlation engine',
      'Email support',
      'Community access (1.0x weight)'
    ]
  },
  {
    name: 'Sharps Room',
    price: 99.99,
    simulations: 100000,
    maxPicksPerDay: 999,
    features: [
      'Unlimited AI picks',
      '100K iteration Monte Carlo sims',
      'Full CLV tracker with history',
      'Advanced analytics dashboards',
      'All prop tools & correlations',
      'Real-time line movement alerts',
      'Priority support',
      'Community access (2.0x weight)'
    ]
  },
  {
    name: 'Founder',
    price: 199.99,
    simulations: 100000,
    maxPicksPerDay: 999,
    limited: true,
    features: [
      'Everything in Sharps Room',
      'Lifetime access guarantee',
      'Founder badge & recognition',
      'Early access to new features',
      'Concierge support',
      'Input on product roadmap',
      'Limited to first 100 members'
    ]
  }
];

interface SubscriptionPlansProps {
  currentTier?: string;
  onSelectPlan?: (tierName: string) => void;
}

const SubscriptionPlans: React.FC<SubscriptionPlansProps> = ({ currentTier, onSelectPlan }) => {
  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-3xl font-bold">Choose Your Edge</h2>
        <p className="text-light-gray">
          Unlock advanced Monte Carlo simulations and beat the closing line
        </p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
        {SUBSCRIPTION_TIERS.map((tier) => (
          <div
            key={tier.name}
            className={`relative bg-charcoal rounded-xl p-6 border-2 transition-all ${
              tier.popular
                ? 'border-electric-blue shadow-lg shadow-electric-blue/20'
                : tier.limited
                ? 'border-gold shadow-lg shadow-gold/20'
                : 'border-navy hover:border-electric-blue/50'
            } ${currentTier === tier.name.toLowerCase() ? 'ring-2 ring-electric-blue' : ''}`}
          >
            {tier.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-electric-blue text-white text-xs font-bold px-4 py-1 rounded-full">
                MOST POPULAR
              </div>
            )}
            {tier.limited && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gold text-navy text-xs font-bold px-4 py-1 rounded-full">
                LIMITED: 100 SPOTS
              </div>
            )}

            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-bold">{tier.name}</h3>
                <div className="mt-2 flex items-baseline">
                  <span className="text-4xl font-bold">${tier.price}</span>
                  <span className="text-light-gray ml-2">/month</span>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex items-center text-light-gray">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
                    <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd" />
                  </svg>
                  {tier.simulations.toLocaleString()} simulations
                </div>
              </div>

              <div className="border-t border-navy pt-4">
                <ul className="space-y-3">
                  {tier.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start text-sm">
                      <svg
                        className="w-5 h-5 text-neon-green mr-2 shrink-0 mt-0.5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                      <span className="text-light-gray">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <button
                onClick={() => onSelectPlan?.(tier.name.toLowerCase().replace(' ', '_'))}
                disabled={currentTier === tier.name.toLowerCase().replace(' ', '_')}
                className={`w-full py-3 rounded-lg font-semibold transition-all ${
                  currentTier === tier.name.toLowerCase().replace(' ', '_')
                    ? 'bg-navy text-light-gray cursor-not-allowed'
                    : tier.popular || tier.limited
                    ? 'bg-electric-blue hover:bg-electric-blue/90 text-white'
                    : 'bg-charcoal border border-electric-blue text-electric-blue hover:bg-electric-blue hover:text-white'
                }`}
              >
                {currentTier === tier.name.toLowerCase().replace(' ', '_')
                  ? 'Current Plan'
                  : 'Select Plan'}
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-charcoal rounded-xl p-6 border border-navy">
        <h3 className="text-lg font-bold mb-4">🔥 Simulation Power = Your Edge</h3>
        <div className="grid md:grid-cols-4 gap-6">
          <div className="space-y-2">
            <div className="text-2xl font-bold text-gray-400">10K</div>
            <div className="text-sm text-light-gray">
              Free Tier - Basic precision for casual bettors
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-2xl font-bold text-blue-400">25K</div>
            <div className="text-sm text-light-gray">
              Starter ($19.99) - 2.5x more precise than free
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-2xl font-bold text-purple-400">50K</div>
            <div className="text-sm text-light-gray">
              Pro ($39.99) - Professional-grade analysis
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-2xl font-bold text-amber-400">75K</div>
            <div className="text-sm text-light-gray">
              Elite ($89) - Institutional-quality precision
            </div>
          </div>
        </div>
        <div className="mt-6 pt-6 border-t border-navy grid md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <div className="text-2xl font-bold text-neon-green">&gt; 3%</div>
            <div className="text-sm text-light-gray">
              Average CLV (Closing Line Value) - consistently beating the market
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-2xl font-bold text-gold">&lt; 0.20</div>
            <div className="text-sm text-light-gray">
              Brier Score - exceptional calibration quality (0 = perfect)
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SubscriptionPlans;
