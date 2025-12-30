import React, { useEffect, useState } from 'react';
import { getSubscriptionStatus } from '../services/api';

interface TierConfig {
  label: string;
  sims: number;
  color: string;
}

const TIERS: Record<string, TierConfig> = {
  starter: { label: "Starter", sims: 10000, color: "text-gray-400" },
  core: { label: "Core", sims: 25000, color: "text-blue-400" },
  pro: { label: "Pro", sims: 50000, color: "text-purple-400" },
  elite: { label: "Elite", sims: 100000, color: "text-gold" },
  founder: { label: "Founder", sims: 100000, color: "text-gold" }
};

const MAX_SIMS = 100000;

interface SimulationPowerWidgetProps {
  onUpgradeClick?: () => void;
}

const SimulationPowerWidget: React.FC<SimulationPowerWidgetProps> = ({ onUpgradeClick }) => {
  const [userTier, setUserTier] = useState<string>('starter');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUserTier = async () => {
      try {
        // The apiRequest function will automatically add the token from localStorage
        const response = await getSubscriptionStatus();
        
        const tier = response.tier || 'starter';
        console.log('✅ User tier loaded:', tier, 'from API response:', response);
        setUserTier(tier.toLowerCase());
      } catch (error) {
        console.error('⚠️ Failed to fetch user tier, defaulting to starter:', error);
        setUserTier('starter');
      } finally {
        setLoading(false);
      }
    };

    fetchUserTier();
  }, []);

  if (loading) return null;

  const currentTier = TIERS[userTier] || TIERS.starter;
  const progressPercent = (currentTier.sims / MAX_SIMS) * 100;

  const getUpgradeMessage = () => {
    switch (userTier) {
      case 'starter':
        return 'Upgrade to Core (25K), Pro (50K) or Elite (100K) for sharper edges.';
      case 'core':
        return 'Upgrade to Pro (50K) or Elite (100K) for higher-resolution projections.';
      case 'pro':
        return 'Elite (100K) runs our maximum simulation depth for complex slates.';
      case 'elite':
      case 'founder':
        return "You're running BeatVegas at full simulation power.";
      default:
        return '';
    }
  };

  const isMaxTier = userTier === 'elite' || userTier === 'founder';

  return (
    <div className="bg-linear-to-br from-charcoal to-navy rounded-lg p-4 border border-gold/20 hover:border-gold/40 transition-all">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-xs text-lightGold/70 mb-1">Simulation Power</div>
          <div className={`text-lg font-bold ${currentTier.color}`}>
            {currentTier.label} · {currentTier.sims.toLocaleString()} sims/game
          </div>
        </div>
        {!isMaxTier && onUpgradeClick && (
          <button
            onClick={onUpgradeClick}
            className="px-3 py-1.5 bg-linear-to-r from-gold to-lightGold text-darkNavy text-xs font-bold rounded hover:shadow-lg hover:shadow-gold/30 transition-all"
          >
            Upgrade
          </button>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="h-2 bg-navy/50 rounded-full overflow-hidden">
          <div
            className="h-full bg-linear-to-r from-electric-blue via-purple-500 to-gold transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          ></div>
        </div>
        <div className="flex justify-between text-[10px] text-lightGold/50 mt-1">
          <span>{currentTier.sims.toLocaleString()}</span>
          <span>{MAX_SIMS.toLocaleString()}</span>
        </div>
      </div>

      {/* Upgrade Message */}
      <div className="text-xs text-lightGold/70 leading-relaxed">
        {isMaxTier ? (
          <span className="text-gold">✓ {getUpgradeMessage()}</span>
        ) : (
          <>
            You're using {currentTier.sims.toLocaleString()} / {MAX_SIMS.toLocaleString()} possible simulations.
            <br />
            <span className="text-lightGold/90">{getUpgradeMessage()}</span>
          </>
        )}
      </div>
    </div>
  );
};

export default SimulationPowerWidget;
