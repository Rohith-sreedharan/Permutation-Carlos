import React from 'react';

// Section 6 — /upgrade pricing page (3-column comparison table)
// Also accessible at /pricing
const TIERS = [
  {
    name: 'Intelligence Preview',
    price: 'Free',
    priceNote: 'No card required',
    cta: null,
    ctaLabel: 'Current Plan',
    ctaClass: 'border border-border-gray text-light-gray cursor-default',
    highlight: false,
    features: [
      '10,000 lifetime Intelligence Cycles',
      '10 decision analyses total',
      'Dashboard access',
      'Public game data',
      'No Telegram channel',
      'No Parlay Builder',
    ],
  },
  {
    name: 'Syndicate',
    price: '$39',
    priceNote: 'per month',
    cta: 'https://beatvegas.app/upgrade',
    ctaLabel: 'Join Syndicate',
    ctaClass: 'border border-yellow-400 text-yellow-400 hover:bg-yellow-400/10',
    highlight: false,
    features: [
      '10,000 Intelligence Cycles/month',
      '10 decision analyses/month — resets monthly',
      'Dashboard access',
      'Telegram channel access',
      'No Parlay Builder',
    ],
  },
  {
    name: 'Platform',
    price: '$97',
    priceNote: 'per month',
    cta: 'https://beatvegas.app/upgrade',
    ctaLabel: 'Upgrade to Platform',
    ctaClass: 'bg-yellow-400 text-[#0a0e1a] hover:bg-yellow-300',
    highlight: true,
    features: [
      '100,000 Intelligence Cycles/month',
      '100 decision analyses/month',
      'Dashboard access',
      'Telegram channel access',
      'Parlay Builder unlocked',
      'Priority support',
    ],
  },
];

export default function UpgradePage() {
  return (
    <div className="min-h-screen bg-[#0a0f1e] flex flex-col items-center justify-start py-16 px-4">
      <div className="w-full max-w-5xl">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-black text-white mb-3">
            Choose Your{' '}
            <span className="bg-gradient-to-r from-yellow-400 to-yellow-300 bg-clip-text text-transparent">
              Plan
            </span>
          </h1>
          <p className="text-light-gray text-lg">
            Intelligence Cycles power every analysis. More cycles — more decisions.
          </p>
        </div>

        {/* 3-column pricing table */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              className={`rounded-2xl border p-8 flex flex-col ${
                tier.highlight
                  ? 'border-yellow-400 bg-[#0f1525]'
                  : 'border-border-gray bg-[#0d1220]'
              }`}
            >
              {tier.highlight && (
                <span className="self-start mb-3 text-xs font-bold uppercase tracking-wider text-yellow-400 border border-yellow-400/40 rounded-full px-3 py-0.5">
                  Most Popular
                </span>
              )}
              <h2 className="text-xl font-bold text-white mb-1">{tier.name}</h2>
              <div className="flex items-baseline gap-1 mb-1">
                <span className="text-4xl font-black text-white">{tier.price}</span>
                {tier.priceNote && (
                  <span className="text-sm text-light-gray">{tier.priceNote}</span>
                )}
              </div>
              <ul className="mt-6 space-y-3 flex-1">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-light-gray">
                    <span className="mt-0.5 text-neon-green shrink-0">✓</span>
                    {f}
                  </li>
                ))}
              </ul>
              <div className="mt-8">
                {tier.cta ? (
                  <a
                    href={tier.cta}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`block w-full text-center font-bold py-3 rounded-lg transition-colors ${tier.ctaClass}`}
                  >
                    {tier.ctaLabel}
                  </a>
                ) : (
                  <span
                    className={`block w-full text-center font-bold py-3 rounded-lg ${tier.ctaClass}`}
                  >
                    {tier.ctaLabel}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* NCPG footer — canonical copy used across all surfaces */}
        <div className="text-center space-y-2 border-t border-border-gray/30 pt-8">
          <p className="text-xs text-light-gray/60">
            BeatVegas provides statistical simulation outputs only — not betting advice.
          </p>
          <p className="text-xs text-light-gray/60">
            Problem gambling help: 1-800-522-4700 |{' '}
            <a
              href="https://www.ncpgambling.org"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-light-gray"
            >
              ncpgambling.org
            </a>
          </p>
          <p className="text-xs text-light-gray/40">
            Prices in USD. Cancel anytime. Billed monthly via Stripe.
          </p>
        </div>
      </div>
    </div>
  );
}
