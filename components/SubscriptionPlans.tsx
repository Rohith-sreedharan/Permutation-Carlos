import React from 'react';
import { PRODUCT_COPY, PRICING_PAGE_COPY, PLAN_IDS, type PlanId } from '../uiCopy/products';

interface SubscriptionPlansProps {
  currentPlan?: PlanId | null;
  onSelectPlan?: (planId: PlanId) => void;
}

const CheckIcon: React.FC = () => (
  <svg className="w-5 h-5 text-neon-green shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
);

const CrossIcon: React.FC = () => (
  <svg className="w-5 h-5 text-light-gray/40 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const SubscriptionPlans: React.FC<SubscriptionPlansProps> = ({ currentPlan, onSelectPlan }) => {
  const telegram = PRODUCT_COPY.TELEGRAM_SYNDICATE;
  const platform = PRODUCT_COPY.BEATVEGAS_PLATFORM;
  const pricing = PRICING_PAGE_COPY;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center space-y-2">
        <h2 className="text-3xl font-bold text-white">{pricing.headline}</h2>
        <p className="text-light-gray">{pricing.subheadline}</p>
      </div>

      {/* Product Cards */}
      <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
        {/* Telegram Syndicate Card */}
        <div className={`relative bg-charcoal rounded-xl p-6 border-2 transition-all ${
          currentPlan === PLAN_IDS.TELEGRAM_SYNDICATE
            ? 'border-electric-blue ring-2 ring-electric-blue'
            : 'border-navy hover:border-electric-blue/50'
        }`}>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-bold text-white">{telegram.name}</h3>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="text-4xl font-bold text-white">$39</span>
                <span className="text-light-gray">/month</span>
              </div>
              <p className="text-sm text-light-gray mt-2">{telegram.oneLiner}</p>
            </div>

            <p className="text-sm text-light-gray leading-relaxed">{telegram.description}</p>

            <div className="border-t border-navy pt-4 space-y-2">
              <p className="text-xs font-semibold text-white uppercase tracking-wide mb-3">Included</p>
              {telegram.included.map((item) => (
                <div key={item} className="flex items-start gap-2 text-sm text-light-gray">
                  <CheckIcon />
                  <span>{item}</span>
                </div>
              ))}
            </div>

            <div className="border-t border-navy pt-4 space-y-2">
              <p className="text-xs font-semibold text-light-gray/50 uppercase tracking-wide mb-3">Not included</p>
              {telegram.notIncluded.map((item) => (
                <div key={item} className="flex items-start gap-2 text-sm text-light-gray/50">
                  <CrossIcon />
                  <span>{item}</span>
                </div>
              ))}
            </div>

            <button
              onClick={() => onSelectPlan?.(PLAN_IDS.TELEGRAM_SYNDICATE)}
              disabled={currentPlan === PLAN_IDS.TELEGRAM_SYNDICATE}
              className={`w-full py-3 rounded-lg font-semibold transition-all ${
                currentPlan === PLAN_IDS.TELEGRAM_SYNDICATE
                  ? 'bg-navy text-light-gray cursor-not-allowed'
                  : 'bg-charcoal border border-electric-blue text-electric-blue hover:bg-electric-blue hover:text-white'
              }`}
            >
              {currentPlan === PLAN_IDS.TELEGRAM_SYNDICATE ? 'Current Plan' : telegram.cta}
            </button>
            <p className="text-xs text-center text-light-gray/50">{telegram.billingNote}</p>
          </div>
        </div>

        {/* Platform Card */}
        <div className={`relative bg-charcoal rounded-xl p-6 border-2 transition-all ${
          currentPlan === PLAN_IDS.BEATVEGAS_PLATFORM
            ? 'border-electric-blue ring-2 ring-electric-blue shadow-lg shadow-electric-blue/20'
            : 'border-gold/60 shadow-lg shadow-gold/10 hover:border-gold'
        }`}>
          <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gold text-navy text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap">
            {platform.badge}
          </div>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-bold text-white">{platform.name}</h3>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="text-4xl font-bold text-white">$149</span>
                <span className="text-light-gray">/month</span>
              </div>
              <p className="text-sm text-light-gray mt-2">{platform.oneLiner}</p>
            </div>

            <p className="text-sm text-light-gray leading-relaxed">{platform.description}</p>

            <div className="border-t border-navy pt-4 space-y-2">
              <p className="text-xs font-semibold text-white uppercase tracking-wide mb-3">Included</p>
              {platform.included.map((item) => (
                <div key={item} className="flex items-start gap-2 text-sm text-light-gray">
                  <CheckIcon />
                  <span>{item}</span>
                </div>
              ))}
            </div>

            <button
              onClick={() => onSelectPlan?.(PLAN_IDS.BEATVEGAS_PLATFORM)}
              disabled={currentPlan === PLAN_IDS.BEATVEGAS_PLATFORM}
              className={`w-full py-3 rounded-lg font-semibold transition-all ${
                currentPlan === PLAN_IDS.BEATVEGAS_PLATFORM
                  ? 'bg-navy text-light-gray cursor-not-allowed'
                  : 'bg-electric-blue hover:bg-electric-blue/90 text-white'
              }`}
            >
              {currentPlan === PLAN_IDS.BEATVEGAS_PLATFORM ? 'Current Plan' : platform.cta}
            </button>
            <p className="text-xs text-center text-light-gray/50">{platform.billingNote}</p>
            <p className="text-xs text-center text-light-gray/50">{platform.billingNoteExtra}</p>
          </div>
        </div>
      </div>

      {/* Comparison Table */}
      <div className="bg-charcoal rounded-xl border border-navy overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-navy">
              <th className="text-left py-3 px-4 text-light-gray font-semibold">Feature</th>
              <th className="text-center py-3 px-4 text-white font-semibold">Telegram Syndicate</th>
              <th className="text-center py-3 px-4 text-gold font-semibold">BeatVegas Platform</th>
            </tr>
          </thead>
          <tbody>
            {pricing.comparisonRows.map((row, i) => (
              <tr key={row.feature} className={`border-b border-navy/50 ${i % 2 === 0 ? 'bg-navy/10' : ''}`}>
                <td className="py-3 px-4 text-light-gray">{row.feature}</td>
                <td className={`py-3 px-4 text-center ${row.telegram === '—' ? 'text-light-gray/30' : 'text-neon-green font-medium'}`}>
                  {row.telegram}
                </td>
                <td className="py-3 px-4 text-center text-neon-green font-medium">
                  {row.platform}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="text-center space-y-1">
        {pricing.tableFooter.map((line) => (
          <p key={line} className="text-xs text-light-gray/60">{line}</p>
        ))}
      </div>
    </div>
  );
};

export default SubscriptionPlans;
