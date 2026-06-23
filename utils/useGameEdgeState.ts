/**
 * useGameEdgeState Hook
 * =====================
 * 
 * ROOT FIX IMPLEMENTATION: Single source of truth for game edge state.
 * 
 * This hook produces the FROZEN GameEdgeState object that ALL UI surfaces
 * MUST read from. No component may independently compute edge status.
 * 
 * ARCHITECTURE:
 * 1. Resolves GameEdgeState from simulation using resolveGameEdgeState
 * 2. Returns read-only state object
 * 3. All render flags are pre-computed
 * 4. All narratives are data-driven templates
 * 5. Fail-closed: null state = render nothing
 */

import { useMemo } from 'react';
import type { MonteCarloSimulation } from '../types';
import type { GameDecisions as CanonicalGameDecisions } from '../types/MarketDecision';
import { 
  GameEdgeState, 
  Classification, 
  ReleaseStatus,
  OfficialAction,
  Grade,
} from './canonicalEdge';
import { resolveGameEdgeState, canPublish, getFailureReasons } from './resolveGameEdgeState';

function getCanonicalSpreadClassification(
  decisions: CanonicalGameDecisions | null | undefined
): Classification | null {
  const raw = String(decisions?.spread?.classification || '').trim().toUpperCase();
  if (!raw) return null;
  if (raw === 'EDGE') return Classification.EDGE;
  if (raw === 'LEAN') return Classification.LEAN;
  if (raw === 'MARKET_ALIGNED') return Classification.MARKET_ALIGNED;
  if (raw === 'NO_ACTION') return Classification.NO_ACTION;
  if (raw === 'BLOCKED') return Classification.BLOCKED;
  return Classification.BLOCKED;
}

export interface GameEdgeStateResult {
  // The canonical frozen state - NEVER mutate
  state: GameEdgeState | null;
  
  // Computed status flags (derived from state)
  isLoading: boolean;
  hasError: boolean;
  canRender: boolean;
  
  // Quick access flags
  hasOfficialEdge: boolean;
  hasLean: boolean;
  hasNoAction: boolean;
  isBlocked: boolean;
  
  // Display helpers
  primaryMarket: 'SPREAD' | 'TOTAL' | 'MONEYLINE' | null;
  primaryAction: string;
  primaryGrade: Grade | null;
  
  // Failure tracking
  failureReasons: string[];
}

/**
 * Resolve and cache GameEdgeState from simulation
 * 
 * USAGE:
 * const { state, canRender, hasOfficialEdge } = useGameEdgeState(simulation, eventId, home, away);
 * if (!canRender) return <BlockedStateCard />;
 * return <EdgeCard state={state} />;
 */
export function useGameEdgeState(
  simulation: MonteCarloSimulation | null | undefined,
  canonicalDecisions: CanonicalGameDecisions | null | undefined,
  eventId: string,
  homeTeam: string,
  awayTeam: string
): GameEdgeStateResult {
  return useMemo(() => {
    // Default empty result (fail-closed)
    const emptyResult: GameEdgeStateResult = {
      state: null,
      isLoading: false,
      hasError: true,
      canRender: false,
      hasOfficialEdge: false,
      hasLean: false,
      hasNoAction: true,
      isBlocked: true,
      primaryMarket: null,
      primaryAction: 'No Actionable Signal',
      primaryGrade: null,
      failureReasons: ['No simulation data'],
    };

    const canonicalClassification = getCanonicalSpreadClassification(canonicalDecisions);
    if (!canonicalClassification) {
      return {
        ...emptyResult,
        failureReasons: ['Canonical spread classification missing from decision_records.payload'],
      };
    }
    
    // Handle loading state
    if (simulation === undefined) {
      return { ...emptyResult, isLoading: true, hasError: false };
    }
    
    // Handle null simulation
    if (!simulation) {
      return emptyResult;
    }
    
    // Resolve canonical state
    const state = resolveGameEdgeState(simulation, eventId, homeTeam, awayTeam);
    
    // Handle resolution failure
    if (!state) {
      return {
        ...emptyResult,
        failureReasons: ['Failed to resolve game edge state'],
      };
    }

    // Canonical classification from persisted decision payload always wins.
    state.classification = canonicalClassification;
    if (canonicalClassification === Classification.BLOCKED || canonicalClassification === Classification.NO_ACTION) {
      state.release_status = ReleaseStatus.BLOCKED_BY_MISSING_DATA;
      state.official_action = OfficialAction.NO_ACTION;
      state.official_market = null;
      state.official_side = null;
    }
    
    // Check if we can render this state
    const canRender = canPublish(state);
    const failureReasons = canRender ? [] : getFailureReasons(state);
    
    // Derive quick access flags from state
    const hasOfficialEdge = state.classification === Classification.EDGE;
    const hasLean = state.classification === Classification.LEAN;
    const hasNoAction = state.classification === Classification.NO_ACTION;
    
    const isBlocked = state.release_status !== ReleaseStatus.APPROVED;
    
    // Determine primary market
    let primaryMarket: 'SPREAD' | 'TOTAL' | 'MONEYLINE' | null = null;
    if (state.official_market === 'SPREAD') primaryMarket = 'SPREAD';
    else if (state.official_market === 'TOTAL') primaryMarket = 'TOTAL';
    else if (state.official_market === 'MONEYLINE') primaryMarket = 'MONEYLINE';
    
    // Determine display action
    let primaryAction: string;
    switch (state.official_action) {
      case OfficialAction.TAKE_POINTS:
        primaryAction = `Take ${state.official_side}`;
        break;
      case OfficialAction.LAY_POINTS:
        primaryAction = `Lay with ${state.official_side}`;
        break;
      case OfficialAction.OVER:
        primaryAction = 'Over';
        break;
      case OfficialAction.UNDER:
        primaryAction = 'Under';
        break;
      case OfficialAction.BACK:
        primaryAction = `${homeTeam} Win`;
        break;
      default:
        primaryAction = 'No Actionable Signal';
    }
    
    // Get primary grade
    let primaryGrade: Grade | null = null;
    if (primaryMarket === 'SPREAD') {
      primaryGrade = state.spread_context.grade;
    } else if (primaryMarket === 'TOTAL') {
      primaryGrade = state.total_context.grade;
    }
    
    return {
      state,
      isLoading: false,
      hasError: false,
      canRender,
      hasOfficialEdge,
      hasLean,
      hasNoAction,
      isBlocked,
      primaryMarket,
      primaryAction,
      primaryGrade,
      failureReasons,
    };
  }, [simulation, canonicalDecisions, eventId, homeTeam, awayTeam]);
}

// ===== DISPLAY UTILITIES =====

/**
 * Get classification display text
 */
export function getClassificationText(state: GameEdgeState | null): string {
  if (!state) return 'Data unavailable';
  
  switch (state.classification) {
    case Classification.EDGE:
      return 'Official Edge';
    case Classification.LEAN:
      return 'Model Lean';
    case Classification.MARKET_ALIGNED:
      return 'Market Aligned';
    case Classification.NO_ACTION:
      return 'No Actionable Signal';
    default:
      return 'Unknown';
  }
}

/**
 * Get styling for classification
 */
export function getClassificationStyling(state: GameEdgeState | null): {
  borderColor: string;
  textColor: string;
  bgColor: string;
  icon: string;
} {
  if (!state || state.release_status !== ReleaseStatus.APPROVED) {
    return {
      borderColor: 'border-red-500',
      textColor: 'text-red-400',
      bgColor: 'bg-red-900/20',
      icon: '🚫',
    };
  }
  
  switch (state.classification) {
    case Classification.EDGE:
      return {
        borderColor: 'border-neon-green',
        textColor: 'text-neon-green',
        bgColor: 'bg-neon-green/10',
        icon: '✅',
      };
    case Classification.LEAN:
      return {
        borderColor: 'border-yellow-500',
        textColor: 'text-yellow-400',
        bgColor: 'bg-yellow-900/10',
        icon: '⚠️',
      };
    case Classification.MARKET_ALIGNED:
      return {
        borderColor: 'border-gray-500',
        textColor: 'text-gray-400',
        bgColor: 'bg-gray-800/50',
        icon: '⛔',
      };
    case Classification.NO_ACTION:
      return {
        borderColor: 'border-red-600',
        textColor: 'text-red-400',
        bgColor: 'bg-red-900/20',
        icon: '🚫',
      };
    default:
      return {
        borderColor: 'border-gray-600',
        textColor: 'text-gray-500',
        bgColor: 'bg-gray-800/30',
        icon: '❓',
      };
  }
}

/**
 * Format grade for display
 */
export function formatGrade(grade: Grade | null): string {
  if (!grade) return '—';
  return grade;
}

/**
 * Get grade styling
 */
export function getGradeStyling(grade: Grade | null): {
  textColor: string;
  bgColor: string;
} {
  switch (grade) {
    case Grade.S:
    case Grade.A:
      return { textColor: 'text-green-400', bgColor: 'bg-green-900/30' };
    case Grade.B:
      return { textColor: 'text-blue-400', bgColor: 'bg-blue-900/30' };
    case Grade.C:
      return { textColor: 'text-yellow-400', bgColor: 'bg-yellow-900/30' };
    case Grade.D:
      return { textColor: 'text-orange-400', bgColor: 'bg-orange-900/30' };
    case Grade.F:
      return { textColor: 'text-red-400', bgColor: 'bg-red-900/30' };
    default:
      return { textColor: 'text-gray-400', bgColor: 'bg-gray-800/30' };
  }
}

/**
 * Format confidence for display (bounded 0-100)
 */
export function formatConfidence(value: number): string {
  const bounded = Math.max(0, Math.min(100, value));
  return `${bounded.toFixed(0)}%`;
}

/**
 * Format probability for display (bounded 0-100)
 */
export function formatProbability(value: number): string {
  const bounded = Math.max(0, Math.min(100, value));
  return `${bounded.toFixed(1)}%`;
}

/**
 * Format EV for display
 */
export function formatEV(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}
