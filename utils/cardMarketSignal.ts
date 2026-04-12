/**
 * ZONE 3 SHARED MARKET SIGNAL CARD RENDERER
 * 
 * Single source of truth for rendering market decision cards.
 * Both grid and list views consume this identical logic.
 * NO per-component rendering logic allowed.
 */

import { MarketDecision, Classification } from '../types/MarketDecision';

/**
 * Rendered card properties - output of renderer
 */
export interface RenderedSignalCard {
  // Visual state
  classification: Classification;
  classificationLabel: string;
  classificationColor: {
    bg: string;      // background color
    text: string;    // text color
    border: string;  // border color
    icon: string;    // icon character/name
  };
  
  // Core display
  marketTypeLabel: string;       // "Spread", "Moneyline", "Total"
  selectionLabel: string;        // "Team +6.5", "OVER 227.5", etc.
  
  // Metrics (always shown for EDGE/LEAN)
  edgeDisplay: string | null;    // Formatted edge with unit ("+0.5 pts", "+2.5% EV")
  modelProbDisplay: string;      // "55.2%" or similar
  marketProbDisplay: string;     // "52.1%" or similar
  
  // Probabilities (for decision logic)
  modelProb: number | null;      // Raw 0-1 value
  marketProb: number | null;     // Raw 0-1 value
  
  // Status rendering
  isBlocked: boolean;
  blockedReason: string | null;
  
  // Accessibility
  ariaLabel: string;
}

/**
 * Classification color scheme
 */
const CLASSIFICATION_COLORS = {
  EDGE: {
    bg: 'bg-green-50',
    text: 'text-green-900',
    border: 'border-green-300',
    icon: '✓',
  },
  LEAN: {
    bg: 'bg-blue-50',
    text: 'text-blue-900',
    border: 'border-blue-300',
    icon: '→',
  },
  MARKET_ALIGNED: {
    bg: 'bg-gray-50',
    text: 'text-gray-700',
    border: 'border-gray-300',
    icon: '=',
  },
  BLOCKED: {
    bg: 'bg-red-50',
    text: 'text-red-900',
    border: 'border-red-300',
    icon: '⊘',
  },
  NO_ACTION: {
    bg: 'bg-gray-50',
    text: 'text-gray-700',
    border: 'border-gray-300',
    icon: '−',
  },
};

/**
 * Classification human-readable labels
 */
const CLASSIFICATION_LABELS: Record<Classification, string> = {
  EDGE: 'EDGE',
  LEAN: 'LEAN',
  MARKET_ALIGNED: 'MARKET ALIGNED',
  BLOCKED: 'BLOCKED',
  NO_ACTION: 'No Actionable Signal',
};

/**
 * Main renderer function - process a MarketDecision into renderable card
 */
export function renderMarketSignalCard(decision: MarketDecision | null): RenderedSignalCard {
  // Handle null/blocked decisions
  if (!decision) {
    return {
      classification: 'BLOCKED' as Classification,
      classificationLabel: 'BLOCKED',
      classificationColor: CLASSIFICATION_COLORS.BLOCKED,
      marketTypeLabel: 'Unknown',
      selectionLabel: 'No Data Available',
      edgeDisplay: null,
      modelProbDisplay: '—',
      marketProbDisplay: '—',
      modelProb: null,
      marketProb: null,
      isBlocked: true,
      blockedReason: 'No decision available',
      ariaLabel: 'Decision blocked: no data available',
    };
  }

  // Extract classification with safe fallback
  const classification: Classification = decision.classification || ('BLOCKED' as Classification);
  
  // Extract probabilities
  const modelProb = decision.model_probability ?? decision.probabilities?.model_prob ?? null;
  const marketProb = decision.market_implied_probability ?? decision.probabilities?.market_implied_prob ?? null;

  // Determine blocked state strictly (NO_ACTION is neutral, not blocked)
  const isBlocked = classification === 'BLOCKED';

  // Get blocked reason if applicable
  let blockedReason: string | null = null;
  if (isBlocked && decision.risk?.blocked_reason) {
    blockedReason = decision.risk.blocked_reason;
  }

  // Format market type display
  const marketTypeLabel = decision.market_type_display || formatMarketType(decision.market_type);

  // Format selection label
  let selectionLabel = decision.selection_label || formatSelectionLabel(decision);
  if (classification === 'BLOCKED') {
    selectionLabel = 'ANALYSIS UNAVAILABLE';
  } else if (classification === 'MARKET_ALIGNED') {
    selectionLabel = 'No actionable signal';
  }

  // Format edge display
  const edgeDisplay = classification === 'EDGE' || classification === 'LEAN'
    ? formatEdgeDisplay(decision)
    : null;

  // Format probabilities for display (suppressed for BLOCKED)
  const modelProbDisplay = classification === 'BLOCKED'
    ? '—'
    : (modelProb !== null ? `${Math.round(modelProb * 100)}%` : '—');
  const marketProbDisplay = classification === 'BLOCKED'
    ? '—'
    : (marketProb !== null ? `${Math.round(marketProb * 100)}%` : '—');

  // Get color scheme
  const classificationColor = CLASSIFICATION_COLORS[classification] || CLASSIFICATION_COLORS.BLOCKED;
  const classificationLabel = CLASSIFICATION_LABELS[classification] || 'UNKNOWN';

  // Build aria label for accessibility
  const ariaLabel = buildAriaLabel(decision, classificationLabel, selectionLabel, edgeDisplay);

  return {
    classification,
    classificationLabel,
    classificationColor,
    marketTypeLabel,
    selectionLabel,
    edgeDisplay,
    modelProbDisplay,
    marketProbDisplay,
    modelProb,
    marketProb,
    isBlocked,
    blockedReason,
    ariaLabel,
  };
}

/**
 * Format market type for display
 */
function formatMarketType(marketType: string): string {
  const typeMap: Record<string, string> = {
    SPREAD: 'Spread',
    MONEYLINE_2WAY: 'Moneyline',
    MONEYLINE_3WAY: 'Moneyline',
    TOTAL: 'Total',
  };
  return typeMap[marketType] || 'Market';
}

/**
 * Format selection label (team/side with line)
 */
function formatSelectionLabel(decision: MarketDecision): string {
  if (decision.selection_label) {
    return decision.selection_label;
  }

  const marketType = decision.market_type;
  const market = decision.market;
  const pick = decision.pick;

  if (!pick || !market) {
    return '—';
  }

  if (marketType === 'SPREAD' || marketType === 'MONEYLINE_2WAY') {
    const pickSpread = pick as any;
    const teamName = pickSpread.team_name || '—';
    const line = (market as any).line ?? '';
    if (line) {
      return `${teamName} ${line > 0 ? '+' : ''}${line}`;
    }
    return teamName;
  }

  if (marketType === 'TOTAL') {
    const pickTotal = pick as any;
    const side = pickTotal.side || 'OVER';
    const line = (market as any).line ?? '—';
    return `${side} ${line}`;
  }

  return '—';
}

/**
 * Format edge for display with appropriate unit
 */
function formatEdgeDisplay(decision: MarketDecision): string | null {
  if (!decision.edge_points && decision.edge_points !== 0) {
    return null;
  }

  const marketType = decision.market_type;
  
  if (marketType === 'SPREAD' || marketType === 'TOTAL') {
    const pts = decision.edge_points;
    return `${pts > 0 ? '+' : ''}${pts.toFixed(1)} pts`;
  }

  if (marketType === 'MONEYLINE_2WAY' || marketType === 'MONEYLINE_3WAY') {
    const ev = decision.edge?.edge_ev ?? decision.edge_points;
    if (ev !== null && ev !== undefined) {
      return `${ev > 0 ? '+' : ''}${(ev * 100).toFixed(1)}% EV`;
    }
  }

  return null;
}

/**
 * Build accessible aria label
 */
function buildAriaLabel(
  decision: MarketDecision,
  classification: string,
  selection: string,
  edge: string | null
): string {
  let label = `${classification} on ${selection}`;
  if (edge) {
    label += ` with ${edge} edge`;
  }
  if (decision.risk?.blocked_reason) {
    label += `. Blocked: ${decision.risk.blocked_reason}`;
  }
  return label;
}

/**
 * Get sport league from game context
 */
export function getSportLabel(league: string): string {
  const sportMap: Record<string, string> = {
    NBA: 'NBA',
    NFL: 'NFL',
    NCAAB: 'NCAAB',
    NCAAF: 'NCAAF',
    NHL: 'NHL',
    MLB: 'MLB',
    WNBA: 'WNBA',
  };
  return sportMap[league?.toUpperCase()] || league || 'Sports';
}

/**
 * Helper to check if card should be displayed (for filtering logic)
 */
export function shouldDisplayCard(decision: MarketDecision | null): boolean {
  if (!decision) return false;
  if (decision.classification === 'NO_ACTION') return false;
  return true;
}

/**
 * Helper to sort cards by classification priority
 */
export const CLASSIFICATION_PRIORITY: Record<Classification, number> = {
  EDGE: 1,        // Show first
  LEAN: 2,
  MARKET_ALIGNED: 3,
  BLOCKED: 4,
  NO_ACTION: 5,   // Show last (or filter out)
};

export function compareCardsByClassification(
  cardA: RenderedSignalCard,
  cardB: RenderedSignalCard
): number {
  const priorityA = CLASSIFICATION_PRIORITY[cardA.classification] ?? 999;
  const priorityB = CLASSIFICATION_PRIORITY[cardB.classification] ?? 999;
  return priorityA - priorityB;
}
