/**
 * Edge State System — Separates Actionable vs Informational Signals
 * 
 * CRITICAL UX FIX: Prevents "EDGE DETECTED" contradictions
 * 
 * Master States:
 * - ACTIONABLE_EDGE: Eligible for PickPlay, premium publishing
 * - MODEL_SIGNAL_HIGH_VARIANCE: Informational only, no action highlight
 * - NO_EDGE: Fully suppressed
 */

export enum EdgeState {
  ACTIONABLE_EDGE = 'actionable_edge',
  MODEL_SIGNAL_HIGH_VARIANCE = 'model_signal_high_variance',
  NO_EDGE = 'no_edge'
}

export interface EdgeClassification {
  state: EdgeState;
  side: string | null;  // 'OVER', 'UNDER', 'FAVORITE', 'UNDERDOG', or null
  magnitude: number;    // Point edge
  probability: number;  // Win/cover probability
  reason: string;       // User-facing explanation
  actionable: boolean;  // Can be highlighted/published
  showBanner: boolean;  // Display "EDGE DETECTED" banner
}

/**
 * Classify spread edge into actionable vs informational
 * 
 * RULE: High volatility OR low confidence blocks actionable edge
 * EXCEPTION: Extreme edge (≥6 pts) with strong consensus (≥70% conf) overrides
 */
export function classifySpreadEdge(
  spreadDeviation: number,
  volatility: number,
  confidence: number,
  valueSide: string | null
): EdgeClassification {
  // Check for exceptional edge that overrides volatility concerns
  const hasExceptionalEdge = spreadDeviation >= 6.0 && confidence >= 70 && volatility < 400;
  
  // High volatility or low confidence blocks actionable edge
  const blockedByRiskControls = (volatility > 300 || confidence < 60) && !hasExceptionalEdge;
  
  // No significant deviation
  if (spreadDeviation < 3.0) {
    return {
      state: EdgeState.NO_EDGE,
      side: null,
      magnitude: spreadDeviation,
      probability: 0.5,
      reason: 'No significant mispricing detected (< 3 pts)',
      actionable: false,
      showBanner: false
    };
  }
  
  // Signal detected but blocked by risk controls
  if (blockedByRiskControls) {
    return {
      state: EdgeState.MODEL_SIGNAL_HIGH_VARIANCE,
      side: valueSide,
      magnitude: spreadDeviation,
      probability: 0.5,
      reason: `Model mispricing detected (${spreadDeviation.toFixed(1)} pts) but blocked by risk controls: ${
        volatility > 300 ? `High volatility (σ=${volatility.toFixed(0)})` : 
        `Low confidence (${confidence}%)`
      }. Not actionable.`,
      actionable: false,
      showBanner: false  // DO NOT show "EDGE DETECTED"
    };
  }
  
  // Actionable edge
  return {
    state: EdgeState.ACTIONABLE_EDGE,
    side: valueSide,
    magnitude: spreadDeviation,
    probability: 0.55 + (spreadDeviation / 40),  // Rough estimate
    reason: `Actionable edge: ${spreadDeviation.toFixed(1)} point mispricing with ${confidence}% confidence`,
    actionable: true,
    showBanner: true
  };
}

/**
 * Classify total edge into actionable vs informational
 * 
 * RULE: Block if volatility HIGH, confidence LOW, or EV ≤ 0
 */
export function classifyTotalEdge(
  totalDeviation: number,
  overProb: number,
  underProb: number,
  volatility: number,
  confidence: number,
  expectedValue: number
): EdgeClassification {
  // No significant deviation
  if (totalDeviation < 3.0) {
    return {
      state: EdgeState.NO_EDGE,
      side: null,
      magnitude: totalDeviation,
      probability: 0.5,
      reason: `Model projects within statistical noise (Δ ${totalDeviation.toFixed(1)} pts)`,
      actionable: false,
      showBanner: false
    };
  }
  
  // Determine side
  const side = overProb > 55 ? 'OVER' : underProb > 55 ? 'UNDER' : null;
  const sideProb = side === 'OVER' ? overProb : underProb;
  
  if (!side) {
    return {
      state: EdgeState.NO_EDGE,
      side: null,
      magnitude: totalDeviation,
      probability: 0.5,
      reason: 'Probabilities near 50% — no directional edge',
      actionable: false,
      showBanner: false
    };
  }
  
  // Check risk controls
  const blockedByVolatility = volatility > 300;
  const blockedByConfidence = confidence < 60;
  const blockedByEV = expectedValue <= 0;
  
  if (blockedByVolatility || blockedByConfidence || blockedByEV) {
    return {
      state: EdgeState.MODEL_SIGNAL_HIGH_VARIANCE,
      side: side,
      magnitude: totalDeviation,
      probability: sideProb / 100,
      reason: `Model signal detected (${side}, ${sideProb.toFixed(0)}% probability, ${totalDeviation.toFixed(1)} pt edge) but blocked: ${
        blockedByVolatility ? `High volatility (σ=${volatility.toFixed(0)})` :
        blockedByConfidence ? `Low confidence (${confidence}%)` :
        `Negative EV (${expectedValue.toFixed(2)}%)`
      }. Informational only.`,
      actionable: false,
      showBanner: false  // CRITICAL: No "EDGE DETECTED" banner
    };
  }
  
  // Actionable edge
  return {
    state: EdgeState.ACTIONABLE_EDGE,
    side: side,
    magnitude: totalDeviation,
    probability: sideProb / 100,
    reason: `Actionable edge: ${side} ${totalDeviation.toFixed(1)} point mispricing, ${sideProb.toFixed(0)}% probability, +${expectedValue.toFixed(1)}% EV`,
    actionable: true,
    showBanner: true
  };
}

/**
 * Get UI styling for edge state
 */
export function getEdgeStateStyling(state: EdgeState): {
  borderColor: string;
  bgColor: string;
  textColor: string;
  icon: string;
  label: string;
} {
  switch (state) {
    case EdgeState.ACTIONABLE_EDGE:
      return {
        borderColor: 'border-neon-green',
        bgColor: 'bg-neon-green/10',
        textColor: 'text-neon-green',
        icon: '✅',
        label: 'ACTIONABLE EDGE'
      };
    
    case EdgeState.MODEL_SIGNAL_HIGH_VARIANCE:
      return {
        borderColor: 'border-vibrant-yellow',
        bgColor: 'bg-vibrant-yellow/10',
        textColor: 'text-vibrant-yellow',
        icon: '⚠️',
        label: 'MODEL SIGNAL (HIGH VARIANCE)'
      };
    
    case EdgeState.NO_EDGE:
      return {
        borderColor: 'border-gold',
        bgColor: 'bg-gold/5',
        textColor: 'text-gold',
        icon: '⚖️',
        label: 'NO EDGE'
      };
  }
}

/**
 * Should display side highlight (colored pill/badge)?
 * 
 * RULE: Only highlight if actionable
 * If state is NEUTRAL or blocked, grey out
 */
export function shouldHighlightSide(classification: EdgeClassification): boolean {
  return classification.actionable && classification.side !== null;
}

/**
 * Get display text for blocked signal
 * 
 * When signal detected but not actionable, show informational message
 */
export function getBlockedSignalMessage(classification: EdgeClassification): string {
  if (classification.state !== EdgeState.MODEL_SIGNAL_HIGH_VARIANCE) {
    return '';
  }
  
  return `📊 ${classification.side ? `${classification.side} signal` : 'Signal'} detected but blocked by risk controls. ${classification.reason}`;
}
