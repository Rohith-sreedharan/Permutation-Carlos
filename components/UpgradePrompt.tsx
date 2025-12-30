/**
 * Contextual Upgrade Prompts
 * 
 * Shows upgrade messaging when users hit tier limitations.
 * Clean, classy, non-annoying prompts tied to simulation depth.
 */

import React from 'react';

type UpgradeVariant = 'short' | 'medium' | 'long' | 'chart' | 'props' | 'confidence' | 'share' | 'firsthalf';

interface UpgradePromptProps {
  variant: UpgradeVariant;
  currentTier: string;
  currentIterations: number;
  show?: boolean;
  className?: string;
}

const TIER_LIMITS = {
  free: 10000,
  explorer: 25000,
  pro: 50000,
  elite: 100000
};

const getTierName = (tier: string): string => {
  const names: Record<string, string> = {
    free: 'Free',
    explorer: 'Explorer',
    pro: 'Pro',
    elite: 'Elite'
  };
  return names[tier.toLowerCase()] || 'Free';
};

const getNextTier = (currentTier: string): { name: string; iterations: number; price: string } => {
  const tier = currentTier.toLowerCase();
  
  if (tier === 'free' || tier === 'explorer') {
    return { name: 'Pro', iterations: 50000, price: '$49/mo' };
  }
  
  if (tier === 'pro') {
    return { name: 'Elite', iterations: 100000, price: '$199/mo' };
  }
  
  return { name: 'Elite', iterations: 100000, price: '$199/mo' };
};

const UpgradePrompt: React.FC<UpgradePromptProps> = ({
  variant,
  currentTier,
  currentIterations,
  show = true,
  className = ''
}) => {
  // Don't show if user is already at max tier
  const tier = currentTier.toLowerCase();
  if (tier === 'elite' || tier === 'admin' || tier === 'founder' || tier === 'internal' || tier === 'platinum') {
    return null;
  }
  
  // Don't show if explicitly hidden
  if (!show) {
    return null;
  }
  
  // Don't show if iterations are already high (50K+)
  if (currentIterations >= 50000 && variant !== 'share') {
    return null;
  }
  
  const nextTier = getNextTier(currentTier);
  
  const handleUpgrade = () => {
    window.location.href = '/settings?tab=subscription';
  };
  
  // Variant-specific content
  const getContent = () => {
    switch (variant) {
      case 'short':
        return (
          <div className="flex items-center justify-between text-xs">
            <span className="text-light-gray">
              Powered by {(currentIterations / 1000).toFixed(0)}K simulations
            </span>
            <button
              onClick={handleUpgrade}
              className="text-gold hover:text-yellow-300 font-semibold transition"
            >
              Upgrade for more precision →
            </button>
          </div>
        );
      
      case 'medium':
        return (
          <div className="bg-linear-to-r from-gold/10 to-purple-600/10 rounded-lg p-3 border border-gold/30">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white text-sm font-semibold mb-1">
                  Upgrade to unlock higher-precision simulations
                </div>
                <div className="text-light-gray text-xs">
                  More accurate projections and full data resolution
                </div>
              </div>
              <button
                onClick={handleUpgrade}
                className="bg-gold text-charcoal px-4 py-2 rounded-lg font-bold text-sm hover:bg-yellow-400 transition"
              >
                Upgrade
              </button>
            </div>
          </div>
        );
      
      case 'long':
        return (
          <div className="bg-linear-to-r from-gold/10 to-purple-600/10 rounded-lg p-4 border border-gold/30">
            <div className="text-gold text-xs uppercase font-bold mb-2">
              ⚡ Unlock Full Power
            </div>
            <div className="text-white text-sm font-semibold mb-2">
              Your current tier gives limited simulation depth
            </div>
            <div className="text-light-gray text-xs mb-3">
              Upgrading unlocks {nextTier.iterations.toLocaleString()} simulations, sharper projections, 
              stronger confidence scores, and full Monte Carlo granularity.
            </div>
            <button
              onClick={handleUpgrade}
              className="bg-gold text-charcoal px-6 py-2 rounded-lg font-bold text-sm hover:bg-yellow-400 transition w-full"
            >
              Upgrade to {nextTier.name} ({nextTier.price})
            </button>
          </div>
        );
      
      case 'chart':
        return (
          <div className="text-center py-2 bg-navy/30 rounded-lg border border-gold/20">
            <div className="text-light-gray text-xs">
              🔒 Unlock full Monte Carlo detail with higher simulation tiers
            </div>
            <button
              onClick={handleUpgrade}
              className="text-gold hover:text-yellow-300 text-xs font-semibold mt-1 transition"
            >
              Upgrade for sharper curves →
            </button>
          </div>
        );
      
      case 'props':
        return (
          <div className="mt-2 bg-gold/10 rounded-lg p-2 border border-gold/30">
            <div className="text-light-gray text-xs">
              This projection uses {(currentIterations / 1000).toFixed(0)}K simulations.
            </div>
            <button
              onClick={handleUpgrade}
              className="text-gold hover:text-yellow-300 text-xs font-semibold mt-1 transition"
            >
              Upgrade for sharper EV% and deeper prop accuracy →
            </button>
          </div>
        );
      
      case 'confidence':
        return (
          <div className="mt-2 text-center">
            <div className="text-light-gray text-xs">
              Higher simulation tiers increase accuracy and reduce volatility noise
            </div>
            <button
              onClick={handleUpgrade}
              className="text-gold hover:text-yellow-300 text-xs font-semibold mt-1 transition"
            >
              Upgrade for stronger signal →
            </button>
          </div>
        );
      
      case 'share':
        return (
          <div className="bg-linear-to-r from-gold/10 to-purple-600/10 rounded-lg p-4 border border-gold/30 text-center">
            <div className="text-gold text-sm font-bold mb-2">
              📤 Share Premium Projections
            </div>
            <div className="text-light-gray text-xs mb-3">
              Upgrade to share higher-precision (50K–100K) Pro/Elite simulations with exclusive share cards
            </div>
            <button
              onClick={handleUpgrade}
              className="bg-gold text-charcoal px-6 py-2 rounded-lg font-bold text-sm hover:bg-yellow-400 transition"
            >
              Upgrade to {nextTier.name}
            </button>
          </div>
        );
      
      case 'firsthalf':
        return (
          <div className="mt-2 bg-navy/30 rounded-lg p-2 border border-gold/20">
            <div className="text-light-gray text-xs">
              Based on BeatVegas AI-only projections ({(currentIterations / 1000).toFixed(0)}K simulations)
            </div>
            <button
              onClick={handleUpgrade}
              className="text-gold hover:text-yellow-300 text-xs font-semibold mt-1 transition"
            >
              Upgrade for higher precision (50K–100K simulations) →
            </button>
          </div>
        );
      
      default:
        return null;
    }
  };
  
  return (
    <div className={`upgrade-prompt ${className}`}>
      {getContent()}
    </div>
  );
};

export default UpgradePrompt;
