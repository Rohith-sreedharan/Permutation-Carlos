/**
 * ZONE 3: Market Decision Card
 * 
 * Single component for rendering market decisions from the decisions endpoint.
 * Consumed by both grid and list views using identical logic.
 * Uses cardMarketSignal.ts renderer - NO per-component logic.
 */

import React from 'react';
import { AlertCircle, RotateCw } from 'lucide-react';
import { MarketDecision } from '../types/MarketDecision';
import { renderMarketSignalCard, getSportLabel } from '../utils/cardMarketSignal';

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
            {rendered.classificationLabel}
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
            <p className="text-xs text-gray-600 mb-1">Model Prob</p>
            <p className="text-sm font-bold text-blue-900">{rendered.modelProbDisplay}</p>
          </div>
          <div className="bg-gray-50 rounded p-2">
            <p className="text-xs text-gray-600 mb-1">Market Prob</p>
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
