import React, { useEffect, useState } from 'react';
import { getSubscriptionStatus } from '../services/api';
import { COPY } from '../utils/uiCopy';

const TIER_CYCLE_LIMITS: Record<string, number> = {
  intelligence_preview: 10_000,
  syndicate: 10_000,
  telegram_syndicate: 10_000,
  platform: 100_000,
  beatvegas_platform: 100_000,
};
const DEFAULT_PREVIEW_MAX = 10_000;

interface SimulationPowerWidgetProps {
  onUpgradeClick?: () => void;
}

const SimulationPowerWidget: React.FC<SimulationPowerWidgetProps> = ({ onUpgradeClick }) => {
  const [platformAccess, setPlatformAccess] = useState(false);
  const [telegramAccess, setTelegramAccess] = useState(false);
  const [engineCyclesLimit, setEngineCyclesLimit] = useState(0);
  const [tierMaxCycles, setTierMaxCycles] = useState(DEFAULT_PREVIEW_MAX);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEntitlements = async () => {
      try {
        const response = await getSubscriptionStatus();
        setPlatformAccess(Boolean(response.platform_access));
        setTelegramAccess(Boolean(response.telegram_access));
        setEngineCyclesLimit(Number(response.engine_cycles_limit ?? 0));
        // Derive correct max from tier or plan_id
        const tier = response.tier || response.plan_id || '';
        const max = TIER_CYCLE_LIMITS[tier] ?? (response.platform_access ? 100_000 : DEFAULT_PREVIEW_MAX);
        setTierMaxCycles(max);
      } catch (error) {
        console.error('Failed to fetch entitlement state:', error);
        setPlatformAccess(false);
        setTelegramAccess(false);
        setEngineCyclesLimit(0);
        setTierMaxCycles(DEFAULT_PREVIEW_MAX);
      } finally {
        setLoading(false);
      }
    };

    fetchEntitlements();

    // Listen for real-time cycle balance updates emitted by GameDetail
    // after each simulation fetch — no API refetch needed
    const handleCycleUpdate = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail && typeof detail.cycles_used === 'number') {
        setEngineCyclesLimit(detail.cycles_used);
        if (typeof detail.cycles_allocated === 'number' && detail.cycles_allocated > 0) {
          setTierMaxCycles(detail.cycles_allocated);
        }
      }
    };
    window.addEventListener('bv:cycle_update', handleCycleUpdate);
    return () => window.removeEventListener('bv:cycle_update', handleCycleUpdate);
  }, []);

  if (loading) return null;

  const activeCycles = Math.max(0, engineCyclesLimit);
  const progressPercent = Math.min(100, (activeCycles / tierMaxCycles) * 100);
  const isMaxCapacity = activeCycles >= tierMaxCycles;
  const capacityLabel = isMaxCapacity ? 'Max Capacity' : 'Decision Depth: Preview Mode — Upgrade for full access';

  const getUpgradeMessage = () => {
    if (platformAccess && isMaxCapacity) return "You're running BeatVegas at full Decision Depth.";
    if (platformAccess) return 'Platform access is active. Upgrade plan limits to unlock more Intelligence Cycles.';
    if (telegramAccess) return 'Telegram access is active. Platform unlocks Decision Engine cycles and Parlay Architect.';
    return 'Activate Platform access to unlock Decision Engine cycles.';
  };

  return (
    <div className="bg-linear-to-br from-charcoal to-navy rounded-lg p-4 border border-gold/20 hover:border-gold/40 transition-all">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-xs text-lightGold/70 mb-1">{COPY.decisionDepth}</div>
          <div className={`text-lg font-bold ${platformAccess ? 'text-gold' : telegramAccess ? 'text-electric-blue' : 'text-gray-400'}`}>
            {isMaxCapacity ? `${capacityLabel} · ${activeCycles.toLocaleString()} Intelligence Cycles/period` : capacityLabel}
          </div>
        </div>
        {!isMaxCapacity && onUpgradeClick && (
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
          <span>{activeCycles.toLocaleString()}</span>
          <span>{tierMaxCycles.toLocaleString()}</span>
        </div>
      </div>

      {/* Upgrade Message */}
      <div className="text-xs text-lightGold/70 leading-relaxed">
        {isMaxCapacity ? (
          <span className="text-gold">✓ {getUpgradeMessage()}</span>
        ) : (
          <>
            {(() => {
              const costPerAnalysis = 1000;
              const remaining = tierMaxCycles - activeCycles;
              const analysesRemaining = Math.max(0, Math.floor(remaining / costPerAnalysis));
              return (
                <>
                  You're using {activeCycles.toLocaleString()} / {tierMaxCycles.toLocaleString()} possible Intelligence Cycles.
                  {' '}({analysesRemaining} {analysesRemaining === 1 ? 'analysis' : 'analyses'} remaining)
                </>
              );
            })()}
            <br />
            <span className="text-lightGold/90">{getUpgradeMessage()}</span>
          </>
        )}
      </div>
    </div>
  );
};

export default SimulationPowerWidget;
