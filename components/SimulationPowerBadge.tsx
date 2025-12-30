import React from 'react';
import { getTierConfig, getNextTier, MAX_SIMS } from '../utils/simulationTiers';

interface SimulationPowerBadgeProps {
  userTier: string;
  context: 'game' | 'confidence' | 'parlay';
  volatility?: string;
  onUpgradeClick?: () => void;
}

const SimulationPowerBadge: React.FC<SimulationPowerBadgeProps> = ({
  userTier,
  context,
  volatility,
  onUpgradeClick
}) => {
  const tierConfig = getTierConfig(userTier);
  const nextTier = getNextTier(userTier);
  const isMaxTier = tierConfig.sims >= MAX_SIMS;

  if (context === 'game') {
    return (
      <div className="bg-navy/30 border border-gold/10 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h4 className="text-sm font-bold text-lightGold mb-1">
              Monte Carlo Simulation ({tierConfig.sims.toLocaleString()} iterations – {tierConfig.label} {isMaxTier ? 'max' : 'cap'})
            </h4>
            {!isMaxTier && (
              <div className="text-xs text-lightGold/70">
                {nextTier ? `${nextTier.label} & Elite tiers` : 'Elite tier'} run this game at {nextTier ? nextTier.sims.toLocaleString() : MAX_SIMS.toLocaleString()}\u2013{MAX_SIMS.toLocaleString()} sims for tighter edges.
              </div>
            )}
            {isMaxTier && (
              <div className="text-xs text-gold/80">
                Running at full BeatVegas simulation depth.
              </div>
            )}
          </div>
          {!isMaxTier && onUpgradeClick && (
            <button
              onClick={onUpgradeClick}
              className="px-3 py-1.5 bg-linear-to-r from-gold to-lightGold text-darkNavy text-xs font-bold rounded hover:shadow-lg transition-all"
            >
              🔓 Upgrade to {nextTier?.label}
            </button>
          )}
        </div>
        {!isMaxTier && (
          <div className="text-[10px] text-lightGold/50 mt-2">
            Upgrade to {nextTier?.label || 'Elite'} for {nextTier ? (nextTier.sims / 1000).toFixed(0) : '100'}K sims/game
          </div>
        )}
      </div>
    );
  }

  if (context === 'confidence') {
    return (
      <div className="mt-2">
        <div className="text-xs text-lightGold/70">
          {tierConfig.sims.toLocaleString()} sims active{!isMaxTier && ` · ${tierConfig.label} Tier`}
        </div>
        {!isMaxTier && (
          <div className="text-xs text-lightGold/60 mt-1">
            {nextTier?.label || 'Elite'} tier{nextTier ? 's' : ''} use {nextTier ? nextTier.sims.toLocaleString() : MAX_SIMS.toLocaleString()}\u2013{MAX_SIMS.toLocaleString()} sims on this matchup.
          </div>
        )}
        {volatility === 'HIGH' && !isMaxTier && (
          <div className="mt-3 p-3 bg-orange-500/10 border border-orange-500/30 rounded">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="text-xs font-semibold text-orange-400 mb-1">
                  ⚠️ High-variance matchup detected
                </div>
                <div className="text-xs text-lightGold/70">
                  More simulation power can reduce noise in spots like this.
                </div>
              </div>
              {onUpgradeClick && (
                <button
                  onClick={onUpgradeClick}
                  className="ml-3 px-3 py-1.5 bg-orange-500/20 border border-orange-500/50 text-orange-400 text-xs font-bold rounded hover:bg-orange-500/30 transition-all"
                >
                  🔓 Upgrade
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  return null;
};

export default SimulationPowerBadge;
