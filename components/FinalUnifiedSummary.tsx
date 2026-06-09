/**
 * FinalUnifiedSummary Component
 * =============================
 * 
 * ROOT FIX IMPLEMENTATION: Pure read-only consumer of GameEdgeState.
 * 
 * ARCHITECTURE RULES:
 * 1. ALL display values come from GameEdgeState
 * 2. NO independent edge computation
 * 3. Fail-closed: If canRender is false, display blocked state
 * 4. All narratives are data-driven templates from state
 * 5. OFFICIAL EDGE badge shows ONLY when classification === 'EDGE'
 */

import React from 'react';
import type { MonteCarloSimulation } from '../types';
import { 
  useGameEdgeState,
  getClassificationText,
  getClassificationStyling,
  formatGrade,
  getGradeStyling,
  formatConfidence,
  formatProbability,
} from '../utils/useGameEdgeState';
import { 
  Classification, 
  ReleaseStatus,
  GameEdgeState,
} from '../utils/canonicalEdge';

interface FinalUnifiedSummaryProps {
  simulation: MonteCarloSimulation | null;
  eventId: string;
  homeTeam: string;
  awayTeam: string;
}

const PLATFORM_DISCLAIMER = "BeatVegas provides statistical simulation outputs only - not betting advice. Problem gambling help: 1-800-522-4700 | ncpgambling.org";

export const FinalUnifiedSummary: React.FC<FinalUnifiedSummaryProps> = ({
  simulation,
  eventId,
  homeTeam,
  awayTeam,
}) => {
  // GET CANONICAL STATE - Single source of truth
  const { 
    state,
    canRender,
    hasOfficialEdge,
    hasLean,
    hasNoAction,
    isBlocked,
    primaryMarket,
    primaryAction,
    primaryGrade,
    failureReasons,
  } = useGameEdgeState(simulation, eventId, homeTeam, awayTeam);
  
  // Fail-closed: If we can't render, show blocked state
  if (!state || !canRender) {
    return (
      <div className="mb-6 bg-red-900/20 border border-red-500/40 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="text-2xl">🚫</div>
          <h3 className="text-xl font-bold text-red-400 font-teko">ANALYSIS BLOCKED</h3>
        </div>
        <div className="text-sm text-red-300">
          This card failed pre-render assertions and cannot be displayed.
        </div>
        {failureReasons.length > 0 && (
          <ul className="mt-3 text-xs text-red-400 list-disc list-inside">
            {failureReasons.slice(0, 5).map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  
  // Get styling from canonical state
  const classificationStyling = getClassificationStyling(state);
  
  // Extract contexts (read-only)
  const spreadCtx = state.spread_context;
  const totalCtx = state.total_context;
  const renderFlags = state.render_flags;
  const narrative = state.narrative;
  
  // Volatility context from spread context
  const volatility = spreadCtx.volatility_score || totalCtx.volatility_score || 0;
  const volatilityLabel = volatility > 200 ? 'HIGH' : volatility < 80 ? 'LOW' : 'MODERATE';
  const isHighVolatility = volatility > 200;
  
  return (
    <div className="mb-6 bg-linear-to-br from-electric-blue/10 to-purple-900/10 border border-electric-blue/30 rounded-xl p-6">
      {/* Header with OFFICIAL EDGE badge - from render_flags */}
      <div className="flex items-center gap-3 mb-4">
        <div className="text-2xl">🎯</div>
        <h3 className="text-xl font-bold text-white font-teko">FINAL UNIFIED SUMMARY</h3>
        
        {/* OFFICIAL EDGE BADGE - ONLY shows when render_flags.show_official_play */}
        {renderFlags.show_official_play && (
          <div className="ml-auto px-3 py-1 bg-neon-green/20 border border-neon-green rounded-lg text-neon-green font-bold text-xs animate-pulse">
            ✅ Official Edge
          </div>
        )}
        
        {/* LEAN badge */}
        {!renderFlags.show_official_play && hasLean && (
          <div className="ml-auto px-3 py-1 bg-yellow-900/30 border border-yellow-500 rounded-lg text-yellow-400 font-bold text-xs">
            ⚠️ MODEL LEAN
          </div>
        )}
        
        {/* No Actionable Signal badge */}
        {hasNoAction && (
          <div className="ml-auto px-3 py-1 bg-gray-800/50 border border-gray-600 rounded-lg text-gray-400 font-bold text-xs">
            ⛔ No Actionable Signal
          </div>
        )}
      </div>
      
      <div className="space-y-4">
        {/* Spread Analysis - From Canonical State */}
        <MarketAnalysisCard 
          label="Spread Analysis"
          team={spreadCtx.team}
          side={spreadCtx.side}
          grade={spreadCtx.grade}
          edgeGap={spreadCtx.edge_gap}
          confidence={spreadCtx.confidence_score}
          coverProb={spreadCtx.side === 'HOME' ? spreadCtx.cover_probability_home : spreadCtx.cover_probability_away}
          blockingPassed={spreadCtx.blocking_result.all_passed}
          riskLog={spreadCtx.risk_control_log}
          isOfficialEdge={hasOfficialEdge && primaryMarket === 'SPREAD'}
          isLean={hasLean && state.classification === Classification.LEAN}
        />
        
        {/* Total Analysis - From Canonical State */}
        <TotalAnalysisCard
          side={totalCtx.side}
          grade={totalCtx.grade}
          edgeGap={totalCtx.edge_gap}
          confidence={totalCtx.confidence_score}
          overProb={totalCtx.over_probability}
          underProb={totalCtx.under_probability}
          blockingPassed={totalCtx.blocking_result.all_passed}
          riskLog={totalCtx.risk_control_log}
          isOfficialEdge={hasOfficialEdge && primaryMarket === 'TOTAL'}
          isLean={hasLean && state.classification === Classification.LEAN}
        />
        
        {/* Volatility Context - From Canonical State */}
        <div className={`bg-charcoal/50 p-4 rounded-lg border-l-4 ${isHighVolatility ? 'border-bold-red' : volatilityLabel === 'LOW' ? 'border-neon-green' : 'border-gold'}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="text-light-gray text-xs uppercase font-bold">Volatility Context</div>
            <div className={`font-bold text-sm ${isHighVolatility ? 'text-bold-red' : volatilityLabel === 'LOW' ? 'text-neon-green' : 'text-gold'}`}>
              {isHighVolatility ? '🔴' : volatilityLabel === 'LOW' ? '🟢' : '🟡'} {volatilityLabel}
            </div>
          </div>
          <div className="text-xs text-light-gray leading-relaxed">
            {isHighVolatility ? 
              `High variance environment — wider outcome distribution, increased upset potential. Risk controls active.` :
              volatilityLabel === 'LOW' ? 
              `Low variance — stable, predictable scoring range.` :
              `Moderate variance — normal outcome distribution.`}
          </div>
        </div>
        
        {/* Action Summary - From Canonical State narrative */}
        <div className="bg-linear-to-r from-gold/10 to-purple-500/10 border border-gold/40 rounded-lg p-4">
          <div className="text-light-gray text-xs uppercase mb-2 font-bold">Action Summary</div>
          <div className="text-white font-semibold text-sm leading-relaxed">
            {narrative.action_summary}
          </div>
          
          {/* Edge explanation if official */}
          {hasOfficialEdge && narrative.edge_explanation && (
            <div className="mt-2 text-xs text-neon-green bg-neon-green/10 border border-neon-green/30 rounded px-2 py-1">
              💡 {narrative.edge_explanation}
            </div>
          )}
          
          {/* Risk control summary if any */}
          {narrative.risk_control_summary && (() => {
            const raw = narrative.risk_control_summary;
            // Strip leading "Blocked: " prefix and trailing period to get individual reasons
            const stripped = raw.replace(/^Blocked:\s*/i, '').replace(/\.$/, '');
            const reasons = stripped.split(', ').map(r => r.trim()).filter(Boolean);
            return (
              <div className="mt-2 text-xs text-yellow-400 bg-yellow-900/10 border border-yellow-500/30 rounded px-2 py-2">
                <div className="font-semibold mb-1">⚠️ Blocked</div>
                <ul className="space-y-0.5">
                  {reasons.map((r, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-yellow-500 shrink-0">•</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })()}
        </div>
        
        {/* Snapshot & Version Info */}
        <div className="text-xs text-gray-500 text-right">
          Resolver v{state.resolver_version} | Snapshot: {state.snapshot_hash.slice(0, 8)}
        </div>
        
        {/* Platform Disclaimer */}
        <div className="text-xs text-light-gray/70 text-center pt-2 border-t border-navy/50">
          {PLATFORM_DISCLAIMER}
        </div>
      </div>
    </div>
  );
};

// ===== HELPER COMPONENTS =====

interface MarketAnalysisCardProps {
  label: string;
  team: string | null;
  side: 'HOME' | 'AWAY' | null;
  grade: string | null;
  edgeGap: number;
  confidence: number;
  coverProb: number;
  blockingPassed: boolean;
  riskLog: string[];
  isOfficialEdge: boolean;
  isLean: boolean;
}

const MarketAnalysisCard: React.FC<MarketAnalysisCardProps> = ({
  label,
  team,
  side,
  grade,
  edgeGap,
  confidence,
  coverProb,
  blockingPassed,
  riskLog,
  isOfficialEdge,
  isLean,
}) => {
  const borderColor = isOfficialEdge ? 'border-neon-green' : isLean ? 'border-yellow-500' : 'border-gray-600';
  const statusColor = isOfficialEdge ? 'text-neon-green' : isLean ? 'text-yellow-400' : 'text-gray-400';
  
  return (
    <div className={`bg-charcoal/50 p-4 rounded-lg border-l-4 ${borderColor}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="text-light-gray text-xs uppercase font-bold">{label}</div>
        <div className={`font-bold text-sm ${statusColor} flex items-center gap-2`}>
          {isOfficialEdge && team ? (
            <span>✅ {team}</span>
          ) : isLean && team ? (
            <span>⚠️ MODEL LEAN</span>
          ) : (
            <span>⛔ No Actionable Signal</span>
          )}
        </div>
      </div>
      <div className="text-xs text-light-gray leading-relaxed">
        {isOfficialEdge && team ? (
          `Approved Edge: ${edgeGap.toFixed(1)} pt mispricing | Cover: ${formatProbability(coverProb)}`
        ) : isLean ? (
          'Blocked by risk controls — informational only'
        ) : (
          'Market appears efficiently priced'
        )}
      </div>
      
      {/* Grade display */}
      {grade && (
        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs text-gray-400">Grade:</span>
          <span className={`text-xs font-bold ${getGradeStyling(grade as any).textColor}`}>
            {grade}
          </span>
        </div>
      )}
      
      {/* Risk control log */}
      {riskLog.length > 0 && (
        <div className="mt-2 text-xs text-yellow-400 bg-yellow-900/10 border border-yellow-500/30 rounded px-2 py-2">
          <ul className="space-y-0.5">
            {[...new Set(riskLog)].map((r, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="shrink-0">🛡️</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Official edge details */}
      {isOfficialEdge && (
        <div className="mt-2 text-xs text-neon-green bg-neon-green/10 border border-neon-green/30 rounded px-2 py-1">
          💡 {edgeGap.toFixed(1)} pt gap • Confidence: {formatConfidence(confidence)}
        </div>
      )}
    </div>
  );
};

interface TotalAnalysisCardProps {
  side: 'OVER' | 'UNDER' | null;
  grade: string | null;
  edgeGap: number;
  confidence: number;
  overProb: number;
  underProb: number;
  blockingPassed: boolean;
  riskLog: string[];
  isOfficialEdge: boolean;
  isLean: boolean;
}

const TotalAnalysisCard: React.FC<TotalAnalysisCardProps> = ({
  side,
  grade,
  edgeGap,
  confidence,
  overProb,
  underProb,
  blockingPassed,
  riskLog,
  isOfficialEdge,
  isLean,
}) => {
  const borderColor = isOfficialEdge ? 'border-electric-blue' : isLean ? 'border-yellow-500' : 'border-gray-600';
  const statusColor = isOfficialEdge ? 'text-electric-blue' : isLean ? 'text-yellow-400' : 'text-gray-400';
  const prob = side === 'OVER' ? overProb : underProb;
  
  return (
    <div className={`bg-charcoal/50 p-4 rounded-lg border-l-4 ${borderColor}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="text-light-gray text-xs uppercase font-bold">Total Analysis</div>
        <div className={`font-bold text-sm ${statusColor} flex items-center gap-2`}>
          {isOfficialEdge && side ? (
            <span>✅ {side}</span>
          ) : isLean && side ? (
            <span>⚠️ MODEL LEAN</span>
          ) : (
            <span>⛔ No Actionable Signal</span>
          )}
        </div>
      </div>
      <div className="text-xs text-light-gray leading-relaxed">
        {isOfficialEdge && side ? (
          `Approved Edge: ${edgeGap.toFixed(1)} pt mispricing | ${side}: ${formatProbability(prob)}`
        ) : isLean ? (
          'Blocked by risk controls — informational only'
        ) : (
          'Market appears efficiently priced'
        )}
      </div>
      
      {/* Grade display */}
      {grade && (
        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs text-gray-400">Grade:</span>
          <span className={`text-xs font-bold ${getGradeStyling(grade as any).textColor}`}>
            {grade}
          </span>
        </div>
      )}
      
      {/* Risk control log */}
      {riskLog.length > 0 && (
        <div className="mt-2 text-xs text-yellow-400 bg-yellow-900/10 border border-yellow-500/30 rounded px-2 py-2">
          <ul className="space-y-0.5">
            {[...new Set(riskLog)].map((r, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="shrink-0">🛡️</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Official edge details */}
      {isOfficialEdge && (
        <div className="mt-2 text-xs text-electric-blue bg-electric-blue/10 border border-electric-blue/30 rounded px-2 py-1">
          💡 {edgeGap.toFixed(1)} pt gap • Confidence: {formatConfidence(confidence)}
        </div>
      )}
    </div>
  );
};

export default FinalUnifiedSummary;
