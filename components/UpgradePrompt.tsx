/**
 * UpgradePrompt — v2.0.1
 *
 * Contextual upgrade bridges per BeatVegas Full Copy Spec v2.0.1.
 * All copy sourced from uiCopy/products.ts.
 * Two plans only: telegram_syndicate ($39) and beatvegas_platform ($149).
 */

import React from 'react';
import {
  UPGRADE_MESSAGING,
  PAYWALL_COPY,
  PLAN_IDS,
  PRICE_DISPLAY,
  type PlanId,
} from '../uiCopy/products';

/**
 * Variant:
 *   'telegram_to_platform'  — primary upgrade bridge (Telegram sub → Platform)
 *   'feature_engine'        — Decision Engine feature-specific bridge
 *   'feature_parlay'        — Parlay Architect feature-specific bridge
 *   'feature_warroom'       — War Room feature-specific bridge
 *   'feature_community'     — Community feature-specific bridge
 *   'no_subscription'       — No active subscription at all
 *   'paywall_platform'      — Platform-only paywall for Telegram subscribers
 *   'paywall_parlay'        — Parlay Architect paywall
 *   'paywall_no_sub'        — General paywall for unauthenticated/none
 */
type UpgradeVariant =
  | 'telegram_to_platform'
  | 'feature_engine'
  | 'feature_parlay'
  | 'feature_warroom'
  | 'feature_community'
  | 'no_subscription'
  | 'paywall_platform'
  | 'paywall_parlay'
  | 'paywall_no_sub';

interface UpgradePromptProps {
  variant: UpgradeVariant;
  currentPlan?: PlanId | null;
  show?: boolean;
  className?: string;
  onUpgrade?: () => void;
  onSecondary?: () => void;
}

const UpgradePrompt: React.FC<UpgradePromptProps> = ({
  variant,
  currentPlan,
  show = true,
  className = '',
  onUpgrade,
  onSecondary,
}) => {
  if (!show) return null;

  const goUpgrade = () => {
    if (onUpgrade) {
      onUpgrade();
    } else {
      window.location.href = '/settings?tab=subscription';
    }
  };

  const goSecondary = () => {
    if (onSecondary) onSecondary();
  };

  const renderContent = () => {
    switch (variant) {
      // ----------------------------------------------------------------
      // Primary upgrade bridge — Telegram → Platform
      // ----------------------------------------------------------------
      case 'telegram_to_platform': {
        const c = UPGRADE_MESSAGING.TELEGRAM_TO_PLATFORM;
        return (
          <div className="bg-charcoal border border-electric-blue/40 rounded-xl p-6 space-y-4">
            <p className="text-lg font-bold text-white">{c.headline}</p>
            <p className="text-sm text-light-gray leading-relaxed">{c.body}</p>
            <div className="text-sm text-white font-semibold">{c.planLine}</div>
            <div className="text-xs text-light-gray/70">{c.includedNote}</div>
            <div className="flex flex-col gap-2">
              <button
                onClick={goUpgrade}
                className="w-full py-3 rounded-lg font-bold bg-electric-blue hover:bg-electric-blue/90 text-white transition-all"
              >
                {c.ctaUpgrade}
              </button>
              <button
                onClick={goSecondary}
                className="w-full py-2 rounded-lg text-sm text-light-gray hover:text-white transition-all"
              >
                {c.ctaStay}
              </button>
            </div>
          </div>
        );
      }

      // ----------------------------------------------------------------
      // Feature-specific bridges
      // ----------------------------------------------------------------
      case 'feature_engine': {
        const c = UPGRADE_MESSAGING.FEATURE_BRIDGES.DECISION_ENGINE;
        return (
          <div className="bg-navy/40 border border-navy rounded-lg p-4 space-y-2">
            <p className="text-sm font-semibold text-white">{c.header}</p>
            <p className="text-xs text-light-gray">{c.price}</p>
            <button onClick={goUpgrade} className="text-electric-blue text-sm font-semibold hover:underline">
              {c.cta}
            </button>
          </div>
        );
      }

      case 'feature_parlay': {
        const c = UPGRADE_MESSAGING.FEATURE_BRIDGES.PARLAY_ARCHITECT;
        return (
          <div className="bg-navy/40 border border-navy rounded-lg p-4 space-y-2">
            <p className="text-sm font-semibold text-white">{c.header}</p>
            <p className="text-xs text-light-gray">{c.body}</p>
            <p className="text-xs text-light-gray">{c.price}</p>
            <button onClick={goUpgrade} className="text-electric-blue text-sm font-semibold hover:underline">
              {c.cta}
            </button>
          </div>
        );
      }

      case 'feature_warroom': {
        const c = UPGRADE_MESSAGING.FEATURE_BRIDGES.WAR_ROOM;
        return (
          <div className="bg-navy/40 border border-navy rounded-lg p-4 space-y-2">
            <p className="text-sm font-semibold text-white">{c.header}</p>
            <p className="text-xs text-light-gray">{c.price}</p>
            <button onClick={goUpgrade} className="text-electric-blue text-sm font-semibold hover:underline">
              {c.cta}
            </button>
          </div>
        );
      }

      case 'feature_community': {
        const c = UPGRADE_MESSAGING.FEATURE_BRIDGES.COMMUNITY;
        return (
          <div className="bg-navy/40 border border-navy rounded-lg p-4 space-y-2">
            <p className="text-sm font-semibold text-white">{c.header}</p>
            <p className="text-xs text-light-gray">{c.price}</p>
            <button onClick={goUpgrade} className="text-electric-blue text-sm font-semibold hover:underline">
              {c.cta}
            </button>
          </div>
        );
      }

      // ----------------------------------------------------------------
      // No subscription at all
      // ----------------------------------------------------------------
      case 'no_subscription': {
        const c = UPGRADE_MESSAGING.NO_SUBSCRIPTION;
        return (
          <div className="bg-charcoal border border-navy rounded-xl p-6 space-y-4">
            <p className="text-sm text-light-gray">{c.body}</p>
            <div className="space-y-3">
              <div className="border border-navy rounded-lg p-4 space-y-2">
                <p className="text-sm font-semibold text-white">{c.telegramLine}</p>
                <p className="text-xs text-light-gray">{c.telegramSub}</p>
                <button
                  onClick={goSecondary}
                  className="w-full py-2 rounded-lg text-sm font-semibold border border-electric-blue text-electric-blue hover:bg-electric-blue hover:text-white transition-all"
                >
                  {c.telegramCta}
                </button>
              </div>
              <div className="border border-gold/40 rounded-lg p-4 space-y-2">
                <p className="text-sm font-semibold text-white">{c.platformLine}</p>
                <p className="text-xs text-light-gray">{c.platformSub}</p>
                <button
                  onClick={goUpgrade}
                  className="w-full py-2 rounded-lg text-sm font-semibold bg-electric-blue hover:bg-electric-blue/90 text-white transition-all"
                >
                  {c.platformCta}
                </button>
              </div>
            </div>
          </div>
        );
      }

      // ----------------------------------------------------------------
      // Platform paywall — Telegram subscriber
      // ----------------------------------------------------------------
      case 'paywall_platform': {
        const c = PAYWALL_COPY.PLATFORM_REQUIRED_TELEGRAM_SUB;
        return (
          <div className="bg-charcoal border border-navy rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">{c.title}</h3>
            <p className="text-sm text-light-gray">{c.body}</p>
            <p className="text-sm text-light-gray/70">{c.currentPlan}</p>
            <div>
              <p className="text-xs font-semibold text-white mb-2">Upgrade includes:</p>
              <ul className="space-y-1">
                {c.upgradeIncludes.map((item) => (
                  <li key={item} className="text-xs text-light-gray flex items-center gap-2">
                    <span className="text-electric-blue">•</span>{item}
                  </li>
                ))}
              </ul>
            </div>
            <p className="text-sm font-semibold text-gold">{c.price}</p>
            <div className="flex flex-col gap-2">
              <button
                onClick={goUpgrade}
                className="w-full py-3 rounded-lg font-bold bg-electric-blue hover:bg-electric-blue/90 text-white transition-all"
              >
                {c.cta}
              </button>
              <button
                onClick={goSecondary}
                className="w-full py-2 rounded-lg text-sm text-light-gray hover:text-white transition-all"
              >
                {c.ctaSecondary}
              </button>
            </div>
          </div>
        );
      }

      // ----------------------------------------------------------------
      // Parlay Architect paywall
      // ----------------------------------------------------------------
      case 'paywall_parlay': {
        const c = PAYWALL_COPY.PARLAY_ARCHITECT_NO_PLATFORM;
        return (
          <div className="bg-charcoal border border-navy rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">{c.title}</h3>
            <p className="text-sm text-light-gray">{c.body}</p>
            <p className="text-sm text-light-gray/70">{c.sub}</p>
            <p className="text-sm font-semibold text-gold">{c.price}</p>
            <div className="flex flex-col gap-2">
              <button
                onClick={goUpgrade}
                className="w-full py-3 rounded-lg font-bold bg-electric-blue hover:bg-electric-blue/90 text-white transition-all"
              >
                {c.cta}
              </button>
              <button
                onClick={goSecondary}
                className="w-full py-2 rounded-lg text-sm text-light-gray hover:text-white transition-all"
              >
                {c.ctaSecondary}
              </button>
            </div>
          </div>
        );
      }

      // ----------------------------------------------------------------
      // No subscription — general paywall
      // ----------------------------------------------------------------
      case 'paywall_no_sub': {
        const c = PAYWALL_COPY.NO_SUBSCRIPTION;
        return (
          <div className="bg-charcoal border border-navy rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">{c.title}</h3>
            <div className="space-y-3">
              <div className="border border-navy rounded-lg p-4 space-y-2">
                <p className="text-sm font-semibold text-white">{c.telegramLine}</p>
                <button
                  onClick={goSecondary}
                  className="w-full py-2 rounded-lg text-sm font-semibold border border-electric-blue text-electric-blue hover:bg-electric-blue hover:text-white transition-all"
                >
                  {c.telegramCta}
                </button>
              </div>
              <div className="border border-gold/40 rounded-lg p-4 space-y-2">
                <p className="text-sm font-semibold text-white">{c.platformLine}</p>
                <button
                  onClick={goUpgrade}
                  className="w-full py-2 rounded-lg text-sm font-semibold bg-electric-blue hover:bg-electric-blue/90 text-white transition-all"
                >
                  {c.platformCta}
                </button>
              </div>
              <button
                onClick={goSecondary}
                className="w-full py-1 text-xs text-light-gray/50 hover:text-light-gray transition-all"
              >
                {c.learnMoreCta}
              </button>
            </div>
          </div>
        );
      }

      default:
        return null;
    }
  };

  return (
    <div className={`upgrade-prompt ${className}`}>
      {renderContent()}
    </div>
  );
};

export default UpgradePrompt;
