/**
 * ZONE 3: Market Decision Card
 * 
 * Single component for rendering market decisions from the decisions endpoint.
 * Consumed by both grid and list views using identical logic.
 * Uses cardMarketSignal.ts renderer - NO per-component logic.
 */

import React, { useState } from 'react';
import { AlertCircle, RotateCw } from 'lucide-react';
import { MarketDecision } from '../types/MarketDecision';
import { renderMarketSignalCard, getSportLabel } from '../utils/cardMarketSignal';

// ── Inline tooltip ────────────────────────────────────────────────────────────
const TT: React.FC<{ tip: string; children: React.ReactNode }> = ({ tip, children }) => {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-flex items-center gap-1">
      {children}
      <span
        className="cursor-help text-gray-400 hover:text-gray-600 text-[10px] select-none"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onTouchStart={() => setShow(v => !v)}
        aria-label="More info"
      >ⓘ</span>
      {show && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-1 w-60 text-xs text-white bg-gray-900 rounded px-3 py-2 shadow-xl pointer-events-none whitespace-normal border border-gray-700">
          {tip}
        </span>
      )}
    </span>
  );
};

// ── Classification tooltip copy ───────────────────────────────────────────────
const CLASSIFICATION_TIPS: Record<string, string> = {
  EDGE: 'Model probability exceeds market-implied probability by a meaningful threshold — a statistically significant divergence.',
  LEAN: 'Directional signal present: model diverges from market, but gap is below the EDGE threshold. Informational only.',
  MARKET_ALIGNED: 'Model and market agree. No divergence detected. No actionable signal.',
};

function getClassificationTip(label: string): string {
  const key = Object.keys(CLASSIFICATION_TIPS).find(k => label.toUpperCase().includes(k));
  return key ? CLASSIFICATION_TIPS[key] : 'Intelligence classification produced by the simulation agent.';
}

interface MarketDecisionCardProps {
  decision: MarketDecision | null;
  league: string;
  gameId: string;
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string;
  onRetry?: () => void;
}

const MarketDecisionCard: React.FC<MarketDecisionCardProps> = ({
  decision,
  league,
  gameId,
  isLoading = false,
  isError = false,
  errorMessage,
  onRetry,
}) => {
  // If loading, show loading state
  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-3/4 mb-3"></div>
        <div className="h-3 bg-gray-100 rounded w-1/2"></div>
      </div>
    );
  }

  // If error, show error state with retry button
  if (isError) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-900">Failed to load decision</p>
            <p className="text-xs text-red-700 mt-1">{errorMessage || 'Unable to fetch market decision'}</p>
            {onRetry && (
              <button
                onClick={onRetry}
                className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-700 transition-colors"
                aria-label="Retry loading decision"
              >
                <RotateCw className="w-4 h-4" />
                Retry
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Render using shared renderer
  const rendered = renderMarketSignalCard(decision);

  const sportLabel = getSportLabel(league);

  return (
    <div
      className={`bg-white border-2 rounded-lg p-4 transition-all ${
        rendered.classificationColor.border
      } ${rendered.isBlocked ? 'opacity-75' : ''}`}
      role="article"
      aria-label={rendered.ariaLabel}
    >
      {/* Header: Sport label + Classification badge */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            {sportLabel}
          </span>
          <span
            className={`text-xs font-bold px-2 py-1 rounded ${
              rendered.classificationColor.bg
            } ${rendered.classificationColor.text}`}
          >
            <TT tip={getClassificationTip(rendered.classificationLabel)}>
              {rendered.classificationLabel}
            </TT>
          </span>
        </div>
        {rendered.isBlocked && rendered.blockedReason && (
          <AlertCircle className={`w-4 h-4 ${rendered.classificationColor.text}`} />
        )}
      </div>

      {/* Core display: Market type + Selection */}
      <div className="mb-3">
        {!rendered.isBlocked && (
          <p className="text-xs text-gray-500 mb-1">{rendered.marketTypeLabel}</p>
        )}
        <p className={`text-lg font-bold ${rendered.classificationColor.text}`}>
          {rendered.selectionLabel}
        </p>
      </div>

      {/* Edge metrics (shown unless blocked) */}
      {!rendered.isBlocked && rendered.edgeDisplay && (
        <div className="mb-3 p-2 bg-gray-50 rounded">
          <p className="text-sm font-semibold text-gray-800">{rendered.edgeDisplay}</p>
        </div>
      )}

      {/* Probabilities display */}
      {!rendered.isBlocked && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-blue-50 rounded p-2">
            <p className="text-xs text-gray-600 mb-1">
              <TT tip="Probability assigned by the simulation model after running deterministic agent iterations.">
                Model Prob
              </TT>
            </p>
            <p className="text-sm font-bold text-blue-900">{rendered.modelProbDisplay}</p>
          </div>
          <div className="bg-gray-50 rounded p-2">
            <p className="text-xs text-gray-600 mb-1">
              <TT tip="Market-implied probability derived from the closing line, after removing the bookmaker's margin (vig).">
                Market Prob
              </TT>
            </p>
            <p className="text-sm font-bold text-gray-900">{rendered.marketProbDisplay}</p>
          </div>
        </div>
      )}

      {/* Blocked reason (if applicable) */}
      {rendered.isBlocked && rendered.blockedReason && (
        <div className="mt-3 p-2 bg-red-50 rounded border border-red-100">
          <p className="text-xs text-red-700 font-medium">{rendered.blockedReason}</p>
        </div>
      )}

      {/* Debug info (development only) */}
      {decision && process.env.NODE_ENV === 'development' && (
        <div className="mt-2 pt-2 border-t border-gray-200">
          <p className="text-xs text-gray-400 font-mono truncate">
            {decision.debug?.trace_id}
          </p>
        </div>
      )}
    </div>
  );
};

export default MarketDecisionCard;
