/**
 * FeatureGate — v2.0.1
 *
 * Renders access-denied UI for Platform-only features.
 * Copy sourced from uiCopy/products.ts.
 */

import React from 'react';
import {
  PAYWALL_COPY,
  UPGRADE_MESSAGING,
  FEATURE_DESCRIPTIONS,
  PLAN_IDS,
  type PlanId,
} from '../uiCopy/products';

type GatedFeature = 'DECISION_ENGINE' | 'PARLAY_ARCHITECT' | 'WAR_ROOM' | 'COMMUNITY' | 'INTELLIGENCE_CYCLES';

interface FeatureGateProps {
  feature: GatedFeature;
  /** User's current plan_id from billing_state */
  currentPlan?: PlanId | null;
  onUpgradeClick?: () => void;
  onDismiss?: () => void;
}

const FEATURE_ICON: Record<GatedFeature, string> = {
  DECISION_ENGINE: '🧠',
  PARLAY_ARCHITECT: '🏗️',
  WAR_ROOM: '⚔️',
  COMMUNITY: '💬',
  INTELLIGENCE_CYCLES: '⚡',
};

type FeatureBridgeCopy = {
  header: string;
  body?: string;
  price: string;
  cta: string;
};

const FeatureGate: React.FC<FeatureGateProps> = ({
  feature,
  currentPlan,
  onUpgradeClick,
  onDismiss,
}) => {
  const isTelegramSub = currentPlan === PLAN_IDS.TELEGRAM_SYNDICATE;
  const hasNoSub = !currentPlan;

  const handleUpgrade = () => {
    if (onUpgradeClick) {
      onUpgradeClick();
    } else {
      window.location.href = '/settings?tab=subscription';
    }
  };

  // Determine copy based on subscription state
  const renderPaywall = () => {
    if (feature === 'PARLAY_ARCHITECT') {
      if (hasNoSub) {
        const c = PAYWALL_COPY.PARLAY_ARCHITECT_NO_PLATFORM;
        return (
          <>
            <h3 className="text-xl font-bold text-white mb-2">{c.title}</h3>
            <p className="text-sm text-light-gray mb-1">{c.body}</p>
            <p className="text-xs text-light-gray/70 mb-4">{c.sub}</p>
            <p className="text-sm font-semibold text-gold mb-4">{c.price}</p>
            <div className="flex flex-col gap-2">
              <button onClick={handleUpgrade} className="px-6 py-3 bg-electric-blue hover:bg-electric-blue/90 text-white font-bold rounded-lg transition-all">
                {c.cta}
              </button>
              {onDismiss && (
                <button onClick={onDismiss} className="text-sm text-light-gray/60 hover:text-light-gray transition-all">
                  {c.ctaSecondary}
                </button>
              )}
            </div>
          </>
        );
      }
      if (isTelegramSub) {
        const c = UPGRADE_MESSAGING.FEATURE_BRIDGES.PARLAY_ARCHITECT;
        return (
          <>
            <h3 className="text-xl font-bold text-white mb-2">{c.header}</h3>
            <p className="text-sm text-light-gray mb-1">{c.body}</p>
            <p className="text-sm font-semibold text-gold mb-4">{c.price}</p>
            <button onClick={handleUpgrade} className="px-6 py-3 bg-electric-blue hover:bg-electric-blue/90 text-white font-bold rounded-lg transition-all">
              {c.cta}
            </button>
          </>
        );
      }
    }

    if (isTelegramSub) {
      const bridgeMap: Partial<Record<GatedFeature, FeatureBridgeCopy>> = {
        DECISION_ENGINE: UPGRADE_MESSAGING.FEATURE_BRIDGES.DECISION_ENGINE,
        WAR_ROOM: UPGRADE_MESSAGING.FEATURE_BRIDGES.WAR_ROOM,
        COMMUNITY: UPGRADE_MESSAGING.FEATURE_BRIDGES.COMMUNITY,
        INTELLIGENCE_CYCLES: UPGRADE_MESSAGING.FEATURE_BRIDGES.DECISION_ENGINE,
      };
      const bridge = bridgeMap[feature] ?? UPGRADE_MESSAGING.FEATURE_BRIDGES.DECISION_ENGINE;
      return (
        <>
          <h3 className="text-xl font-bold text-white mb-2">{bridge.header}</h3>
          <p className="text-sm font-semibold text-gold mb-4">{bridge.price}</p>
          <button onClick={handleUpgrade} className="px-6 py-3 bg-electric-blue hover:bg-electric-blue/90 text-white font-bold rounded-lg transition-all">
            {bridge.cta}
          </button>
        </>
      );
    }

    // No subscription — general paywall
    const c = PAYWALL_COPY.PLATFORM_REQUIRED_TELEGRAM_SUB;
    return (
      <>
        <h3 className="text-xl font-bold text-white mb-2">{c.title}</h3>
        <p className="text-sm text-light-gray mb-1">{c.body}</p>
        <p className="text-sm font-semibold text-gold mb-4">{c.price}</p>
        <div className="flex flex-col gap-2">
          <button onClick={handleUpgrade} className="px-6 py-3 bg-electric-blue hover:bg-electric-blue/90 text-white font-bold rounded-lg transition-all">
            {c.cta}
          </button>
          {onDismiss && (
            <button onClick={onDismiss} className="text-sm text-light-gray/60 hover:text-light-gray transition-all">
              {c.ctaSecondary}
            </button>
          )}
        </div>
      </>
    );
  };

  return (
    <div className="bg-linear-to-br from-charcoal/80 to-navy/80 backdrop-blur-sm rounded-lg border-2 border-navy p-8 text-center">
      <div className="text-5xl mb-3">{FEATURE_ICON[feature]}</div>
      <div className="text-2xl mb-4">🔒</div>
      {renderPaywall()}
    </div>
  );
};

export default FeatureGate;
