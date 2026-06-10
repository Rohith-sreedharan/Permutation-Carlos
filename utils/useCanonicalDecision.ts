/**
 * useCanonicalDecision Hook
 * =========================
 * 
 * Phase 1 Audit Requirement: Single source of truth for all edge decisions.
 * 
 * This hook extracts canonical decisions from simulation market_views.
 * ALL UI components that display edge information MUST read from this hook.
 * 
 * NO independent edge computation is allowed anywhere in the UI.
 * The OFFICIAL EDGE badge MUST only appear when:
 *   validator_status === 'PASS' AND edge_status === 'EDGE'
 */

import { useMemo } from 'react';
import type { 
  MonteCarloSimulation, 
  MarketView,
  CanonicalDecision 
} from '../types';
import { deriveCanonicalDecision, shouldShowOfficialEdge } from '../types';

export interface CanonicalDecisions {
  // Per-market canonical decisions
  spread: CanonicalDecision | null;
  moneyline: CanonicalDecision | null;
  total: CanonicalDecision | null;
  
  // Computed UI flags (derived from canonical decisions)
  hasOfficialSpreadEdge: boolean;
  hasOfficialMoneylineEdge: boolean;
  hasOfficialTotalEdge: boolean;
  hasAnyOfficialEdge: boolean;
  
  // Best market with edge (for top card)
  primaryDecision: CanonicalDecision | null;
  primaryMarket: 'SPREAD' | 'MONEYLINE' | 'TOTAL' | null;
  
  // Snapshot hash for integrity verification
  snapshotHash: string | null;
}

/**
 * Extract canonical decisions from simulation data
 * 
 * CRITICAL: This is the ONLY place where edge decisions are read.
 * NO other code path may compute or derive edge status.
 * 
 * @param simulation - The Monte Carlo simulation response
 * @param eventId - The event ID (required for decision binding)
 */
export function useCanonicalDecision(
  simulation: MonteCarloSimulation | null | undefined,
  eventId: string
): CanonicalDecisions {
  return useMemo(() => {
    // Default empty state
    const emptyResult: CanonicalDecisions = {
      spread: null,
      moneyline: null,
      total: null,
      hasOfficialSpreadEdge: false,
      hasOfficialMoneylineEdge: false,
      hasOfficialTotalEdge: false,
      hasAnyOfficialEdge: false,
      primaryDecision: null,
      primaryMarket: null,
      snapshotHash: null,
    };
    
    if (!simulation || !simulation.market_views) {
      return emptyResult;
    }
    
    const marketViews = simulation.market_views;
    
    // Extract canonical decisions from each market view
    const spread = deriveCanonicalDecision(eventId, marketViews.spread, 'SPREAD');
    const moneyline = deriveCanonicalDecision(eventId, marketViews.moneyline, 'MONEYLINE');
    const total = deriveCanonicalDecision(eventId, marketViews.total, 'TOTAL');
    
    // Compute OFFICIAL EDGE flags using canonical function
    const hasOfficialSpreadEdge = shouldShowOfficialEdge(spread);
    const hasOfficialMoneylineEdge = shouldShowOfficialEdge(moneyline);
    const hasOfficialTotalEdge = shouldShowOfficialEdge(total);
    const hasAnyOfficialEdge = hasOfficialSpreadEdge || hasOfficialMoneylineEdge || hasOfficialTotalEdge;
    
    // Determine primary decision (priority: SPREAD > TOTAL > MONEYLINE)
    let primaryDecision: CanonicalDecision | null = null;
    let primaryMarket: 'SPREAD' | 'MONEYLINE' | 'TOTAL' | null = null;
    
    if (hasOfficialSpreadEdge && spread) {
      primaryDecision = spread;
      primaryMarket = 'SPREAD';
    } else if (hasOfficialTotalEdge && total) {
      primaryDecision = total;
      primaryMarket = 'TOTAL';
    } else if (hasOfficialMoneylineEdge && moneyline) {
      primaryDecision = moneyline;
      primaryMarket = 'MONEYLINE';
    } else {
      // No official edge - use highest gap for informational display
      if (spread && (spread.model_gap_pts >= (total?.model_gap_pts ?? 0)) && 
                    (spread.model_gap_pts >= (moneyline?.model_gap_pts ?? 0))) {
        primaryDecision = spread;
        primaryMarket = 'SPREAD';
      } else if (total && (total.model_gap_pts >= (moneyline?.model_gap_pts ?? 0))) {
        primaryDecision = total;
        primaryMarket = 'TOTAL';
      } else if (moneyline) {
        primaryDecision = moneyline;
        primaryMarket = 'MONEYLINE';
      }
    }
    
    // Use first available snapshot hash
    const snapshotHash = marketViews.spread?.snapshot_hash ?? 
                         marketViews.total?.snapshot_hash ?? 
                         marketViews.moneyline?.snapshot_hash ?? 
                         null;
    
    return {
      spread,
      moneyline,
      total,
      hasOfficialSpreadEdge,
      hasOfficialMoneylineEdge,
      hasOfficialTotalEdge,
      hasAnyOfficialEdge,
      primaryDecision,
      primaryMarket,
      snapshotHash,
    };
  }, [simulation, eventId]);
}

/**
 * Get display text for edge status
 */
export function getEdgeDisplayText(decision: CanonicalDecision | null): string {
  if (!decision) return 'Data unavailable';
  
  if (decision.validator_status !== 'PASS') {
    return `Blocked: ${decision.block_reason || 'Integrity check failed'}`;
  }
  
  switch (decision.edge_status) {
    case 'EDGE':
      return `Official Edge: ${decision.official_side} (${decision.model_gap_pts.toFixed(1)} pts)`;
    case 'LEAN':
      return `Model Lean: ${decision.official_side} — Not official`;
    case 'NO_EDGE':
      return 'Market Aligned — No edge detected';
    case 'BLOCKED':
      return `Blocked: ${decision.block_reason || 'Risk controls active'}`;
    default:
      return 'Analysis unavailable';
  }
}

/**
 * Get styling class for edge status
 */
export function getEdgeStatusStyling(decision: CanonicalDecision | null): {
  borderColor: string;
  textColor: string;
  bgColor: string;
  icon: string;
} {
  if (!decision || decision.validator_status !== 'PASS') {
    return {
      borderColor: 'border-red-500',
      textColor: 'text-red-400',
      bgColor: 'bg-red-900/20',
      icon: '🚫',
    };
  }
  
  switch (decision.edge_status) {
    case 'EDGE':
      return {
        borderColor: 'border-neon-green',
        textColor: 'text-neon-green',
        bgColor: 'bg-neon-green/10',
        icon: '✅',
      };
    case 'LEAN':
      return {
        borderColor: 'border-yellow-500',
        textColor: 'text-yellow-400',
        bgColor: 'bg-yellow-900/10',
        icon: '⚠️',
      };
    case 'NO_EDGE':
      return {
        borderColor: 'border-gray-500',
        textColor: 'text-gray-400',
        bgColor: 'bg-gray-800/50',
        icon: '⛔',
      };
    case 'BLOCKED':
      return {
        borderColor: 'border-red-500',
        textColor: 'text-red-400',
        bgColor: 'bg-red-900/20',
        icon: '🚫',
      };
    default:
      return {
        borderColor: 'border-gray-500',
        textColor: 'text-gray-400',
        bgColor: 'bg-gray-800/50',
        icon: '❓',
      };
  }
}
