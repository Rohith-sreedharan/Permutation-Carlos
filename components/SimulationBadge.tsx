import React from 'react';
import { formatSimulationCount, getUserTierInfo, type TierName } from '../utils/tierConfig';

interface SimulationBadgeProps {
  tier?: TierName;
  simulationCount?: number;
  variance?: number;
  ci95?: [number, number];
  className?: string;
  showUpgradeHint?: boolean;
}

/**
 * SimulationBadge - Displays "Powered by X simulations" with tier branding
 * Now includes variance stability indicator and 95% confidence interval
 */
export default function SimulationBadge({ 
  tier = 'free', 
  simulationCount,
  variance,
  ci95,
  className = '',
  showUpgradeHint = false 
}: SimulationBadgeProps) {
  const tierInfo = getUserTierInfo({ subscription_tier: tier });
  const count = simulationCount || tierInfo.simulations;
  const formattedCount = formatSimulationCount(count);
  
  // Calculate 95% CI range if available
  const ciRange = ci95 && ci95.length === 2 
    ? Math.abs(ci95[1] - ci95[0]) / 2 
    : null;

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <div 
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold backdrop-blur-sm border"
        style={{
          backgroundColor: `${tierInfo.color}15`,
          borderColor: `${tierInfo.color}40`,
          color: tierInfo.color,
        }}
      >
        <svg 
          className="w-3 h-3" 
          fill="currentColor" 
          viewBox="0 0 20 20"
        >
          <path d="M13 7H7v6h6V7z" />
          <path fillRule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h2a2 2 0 012 2v2h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v2a2 2 0 01-2 2h-2v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H5a2 2 0 01-2-2v-2H2a1 1 0 110-2h1V9H2a1 1 0 010-2h1V5a2 2 0 012-2h2V2zM5 5h10v10H5V5z" clipRule="evenodd" />
        </svg>
        <span>Powered by {formattedCount} simulations</span>
      </div>

      {/* Variance Stability Badge */}
      {variance !== undefined && ciRange !== null && (
        <div className="text-[10px] text-gray-400 flex items-center gap-1.5">
          <span className="inline-flex items-center gap-1">
            <span className="text-gray-500">σ={variance.toFixed(1)}</span>
            <span className="text-gray-600">•</span>
            <span className="text-gray-500">±{ciRange.toFixed(1)} pts (95% CI)</span>
          </span>
        </div>
      )}

      {showUpgradeHint && tier === 'free' && (
        <span className="text-xs text-gray-400 italic">
          Upgrade for more precision
        </span>
      )}
    </div>
  );
}
