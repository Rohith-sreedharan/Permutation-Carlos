/**
 * Edge State System v2.0 — 3-State Classification
 * 
 * CRITICAL: Every game resolves to ONE AND ONLY ONE state
 * 
 * Master States (NON-NEGOTIABLE):
 * - OFFICIAL_EDGE: Actionable play, eligible for Telegram & PickPlay
 * - MODEL_LEAN: Informational only, clearly labeled as non-actionable
 * - NO_ACTION: Suppressed - no bet language anywhere
 * 
 * RULE: ONLY OFFICIAL_EDGE can generate betting recommendations
 */

export enum EdgeState {
  OFFICIAL_EDGE = 'official_edge',         // ✅ Actionable play
  MODEL_LEAN = 'model_lean',               // ⚠️ Informational only
  NO_ACTION = 'no_action'                  // ⛔ Suppressed
}

// Confidence reason codes for debugging
export enum ConfidenceReasonCode {
  DISTRIBUTION_STABLE = 'distribution_stable',
  DISTRIBUTION_WIDE = 'distribution_wide',
  DISTRIBUTION_BIMODAL = 'bimodal_distribution',
  HIGH_CONVERGENCE = 'high_convergence',
  LOW_CONVERGENCE = 'low_convergence',
  LOW_VOLATILITY = 'low_volatility',
  HIGH_VOLATILITY = 'high_volatility',
  MARKET_ALIGNED = 'market_aligned',
  MARKET_CONFLICTING = 'market_conflicting',
  MISSING_DATA = 'missing_data',
  CONFIDENCE_UNAVAILABLE = 'confidence_unavailable'
}

export interface ConfidenceComponents {
  distributionScore: number | null;   // 0-1, from std/variance
  convergenceScore: number | null;    // 0-1, from rerun agreement
  volatilityScore: number | null;     // 0-1, inverted volatility
  marketAlignmentScore: number | null; // 0-1, market confirmation
  reasonCodes: ConfidenceReasonCode[];
}

export interface EdgeClassification {
  state: EdgeState;
  side: string | null;  // 'OVER', 'UNDER', 'FAVORITE', 'UNDERDOG', or null
  magnitude: number;    // Point edge
  probability: number;  // Win/cover probability
  confidence: number | null;  // 0-100, null if unavailable
  confidenceComponents: ConfidenceComponents | null;
  reason: string;       // User-facing explanation
  actionable: boolean;  // Can be highlighted/published
  showBanner: boolean;  // Display "EDGE DETECTED" banner
  telegramEligible: boolean;  // Can post to Telegram as play
  stateReasons: string[];     // Why this state was assigned
}

// HYSTERESIS THRESHOLDS - prevent edge flicker
const EDGE_PROMOTE_THRESHOLD = 4.0;   // pts to promote to OFFICIAL_EDGE
const EDGE_DEMOTE_THRESHOLD = 3.0;    // pts to demote from OFFICIAL_EDGE
const CONFIDENCE_PROMOTE_THRESHOLD = 50;  // confidence to promote
const CONFIDENCE_DEMOTE_THRESHOLD = 40;   // confidence to demote

/**
 * Calculate confidence score from components
 * 
 * Confidence = model agreement + stability score
 * NOT win probability, NOT edge size
 * 
 * Formula:
 * confidence = (distribution * 0.40) + (convergence * 0.30) + 
 *              (volatility_inverse * 0.20) + (market_alignment * 0.10)
 */
export function calculateConfidenceScore(
  distributionStd: number | null,
  convergenceStd: number | null,
  volatilityIndex: number | null,
  marketAligned: boolean | null,
  medianValue: number = 100  // Reference for normalization
): { score: number | null; components: ConfidenceComponents } {
  const reasonCodes: ConfidenceReasonCode[] = [];
  
  // Check for missing inputs - DO NOT default to 1%
  const missingInputs = [];
  if (distributionStd === null || distributionStd === undefined) missingInputs.push('distribution');
  if (convergenceStd === null || convergenceStd === undefined) missingInputs.push('convergence');
  if (volatilityIndex === null || volatilityIndex === undefined) missingInputs.push('volatility');
  
  if (missingInputs.length > 0) {
    reasonCodes.push(ConfidenceReasonCode.MISSING_DATA);
    return {
      score: null,  // NOT 1%, show "N/A"
      components: {
        distributionScore: null,
        convergenceScore: null,
        volatilityScore: null,
        marketAlignmentScore: null,
        reasonCodes: [ConfidenceReasonCode.CONFIDENCE_UNAVAILABLE, ...reasonCodes]
      }
    };
  }
  
  // Distribution stability score (40% weight)
  // Lower std relative to median = higher stability
  const stdRef = medianValue * 0.10;  // 10% of median as reference
  const distributionScore = Math.exp(-Math.pow((distributionStd! / stdRef), 2));
  if (distributionScore > 0.7) {
    reasonCodes.push(ConfidenceReasonCode.DISTRIBUTION_STABLE);
  } else if (distributionScore < 0.3) {
    reasonCodes.push(ConfidenceReasonCode.DISTRIBUTION_WIDE);
  }
  
  // Convergence score (30% weight)
  // How consistent are reruns?
  const rerunRef = 1.5;  // Reference std deviation across reruns
  const convergenceScore = Math.exp(-Math.pow((convergenceStd! / rerunRef), 2));
  if (convergenceScore > 0.7) {
    reasonCodes.push(ConfidenceReasonCode.HIGH_CONVERGENCE);
  } else if (convergenceScore < 0.3) {
    reasonCodes.push(ConfidenceReasonCode.LOW_CONVERGENCE);
  }
  
  // Volatility inverse score (20% weight)
  const volRef = 200;  // Reference volatility
  const volatilityScore = 1 / (1 + (volatilityIndex! / volRef));
  if (volatilityScore > 0.6) {
    reasonCodes.push(ConfidenceReasonCode.LOW_VOLATILITY);
  } else if (volatilityScore < 0.3) {
    reasonCodes.push(ConfidenceReasonCode.HIGH_VOLATILITY);
  }
  
  // Market alignment score (10% weight)
  const marketAlignmentScore = marketAligned ? 1.0 : 0.3;
  if (marketAligned) {
    reasonCodes.push(ConfidenceReasonCode.MARKET_ALIGNED);
  } else if (marketAligned === false) {
    reasonCodes.push(ConfidenceReasonCode.MARKET_CONFLICTING);
  }
  
  // Combine with weights
  const rawScore = 
    (distributionScore * 0.40) +
    (convergenceScore * 0.30) +
    (volatilityScore * 0.20) +
    (marketAlignmentScore * 0.10);
  
  // Clamp ONLY at the end, to 0-100
  const finalScore = Math.max(0, Math.min(100, rawScore * 100));
  
  return {
    score: Math.round(finalScore),
    components: {
      distributionScore,
      convergenceScore,
      volatilityScore,
      marketAlignmentScore,
      reasonCodes
    }
  };
}

/**
 * Classify spread edge into 3-state system
 * 
 * Confidence bands:
 * - 70%+ → Very stable (rare, strong EDGE)
 * - 50–69% → Playable EDGE  
 * - 25–49% → MODEL LEAN only
 * - <25% → NO_ACTION (blocked)
 */
export function classifySpreadEdge(
  spreadDeviation: number,
  volatility: number,
  confidence: number | null,
  valueSide: string | null,
  previousState?: EdgeState  // For hysteresis
): EdgeClassification {
  const stateReasons: string[] = [];
  
  // Handle unavailable confidence
  if (confidence === null) {
    stateReasons.push('Confidence unavailable (missing inputs)');
    return {
      state: EdgeState.NO_ACTION,
      side: null,
      magnitude: spreadDeviation,
      probability: 0.5,
      confidence: null,
      confidenceComponents: null,
      reason: 'Model data incomplete — confidence unavailable',
      actionable: false,
      showBanner: false,
      telegramEligible: false,
      stateReasons
    };
  }
  
  // No significant deviation
  if (spreadDeviation < 2.0) {
    stateReasons.push(`Edge magnitude too small (${spreadDeviation.toFixed(1)} pts < 2.0)`);
    return {
      state: EdgeState.NO_ACTION,
      side: null,
      magnitude: spreadDeviation,
      probability: 0.5,
      confidence,
      confidenceComponents: null,
      reason: 'No significant mispricing detected',
      actionable: false,
      showBanner: false,
      telegramEligible: false,
      stateReasons
    };
  }
  
  // Apply hysteresis if we have a previous state
  let effectivePromoteThreshold = EDGE_PROMOTE_THRESHOLD;
  let effectiveDemoteThreshold = EDGE_DEMOTE_THRESHOLD;
  let effectiveConfidencePromote = CONFIDENCE_PROMOTE_THRESHOLD;
  let effectiveConfidenceDemote = CONFIDENCE_DEMOTE_THRESHOLD;
  
  if (previousState === EdgeState.OFFICIAL_EDGE) {
    // Currently an EDGE - use demote thresholds
    effectivePromoteThreshold = EDGE_DEMOTE_THRESHOLD;
    effectiveConfidencePromote = CONFIDENCE_DEMOTE_THRESHOLD;
  }
  
  // Classification logic based on confidence bands
  const isConfidenceBlocked = confidence < 25;
  const isConfidenceLean = confidence >= 25 && confidence < effectiveConfidencePromote;
  const isHighVolatility = volatility > 300;
  
  // NO_ACTION: Confidence < 25% OR (low edge AND high volatility)
  if (isConfidenceBlocked || (spreadDeviation < 3.0 && isHighVolatility)) {
    stateReasons.push(`Confidence too low (${confidence}% < 25%)`);
    if (isHighVolatility) stateReasons.push(`High volatility (σ=${volatility.toFixed(0)})`);
    
    return {
      state: EdgeState.NO_ACTION,
      side: spreadDeviation >= 2.0 ? valueSide : null,
      magnitude: spreadDeviation,
      probability: 0.5,
      confidence,
      confidenceComponents: null,
      reason: 'Model signal blocked by risk controls',
      actionable: false,
      showBanner: false,
      telegramEligible: false,
      stateReasons
    };
  }
  
  // MODEL_LEAN: Confidence 25-49% OR blocked by volatility
  if (isConfidenceLean || (isHighVolatility && confidence < 70)) {
    stateReasons.push(`Confidence in LEAN range (${confidence}%)`);
    if (isHighVolatility) stateReasons.push(`Volatility elevated (σ=${volatility.toFixed(0)})`);
    
    return {
      state: EdgeState.MODEL_LEAN,
      side: valueSide,
      magnitude: spreadDeviation,
      probability: 0.5 + (spreadDeviation / 40),
      confidence,
      confidenceComponents: null,
      reason: `Model lean: ${spreadDeviation.toFixed(1)} pt signal, ${confidence}% confidence — not an official play`,
      actionable: false,
      showBanner: false,
      telegramEligible: false,  // Can post as "Model Lean — Not official"
      stateReasons
    };
  }
  
  // OFFICIAL_EDGE: Confidence >= 50% AND sufficient edge AND not high volatility
  if (spreadDeviation >= effectivePromoteThreshold && confidence >= effectiveConfidencePromote) {
    stateReasons.push(`Edge threshold met (${spreadDeviation.toFixed(1)} pts >= ${effectivePromoteThreshold})`);
    stateReasons.push(`Confidence sufficient (${confidence}% >= ${effectiveConfidencePromote}%)`);
    
    return {
      state: EdgeState.OFFICIAL_EDGE,
      side: valueSide,
      magnitude: spreadDeviation,
      probability: 0.55 + (spreadDeviation / 40),
      confidence,
      confidenceComponents: null,
      reason: `Official edge: ${spreadDeviation.toFixed(1)} pt mispricing, ${confidence}% confidence`,
      actionable: true,
      showBanner: true,
      telegramEligible: true,
      stateReasons
    };
  }
  
  // Default to MODEL_LEAN for edge cases
  stateReasons.push(`Edge in buffer zone (${spreadDeviation.toFixed(1)} pts)`);
  return {
    state: EdgeState.MODEL_LEAN,
    side: valueSide,
    magnitude: spreadDeviation,
    probability: 0.5 + (spreadDeviation / 40),
    confidence,
    confidenceComponents: null,
    reason: `Model signal detected but not meeting all thresholds — informational only`,
    actionable: false,
    showBanner: false,
    telegramEligible: false,
    stateReasons
  };
}

/**
 * Classify total edge into 3-state system
 */
export function classifyTotalEdge(
  totalDeviation: number,
  overProb: number,
  underProb: number,
  volatility: number,
  confidence: number | null,
  expectedValue: number,
  previousState?: EdgeState
): EdgeClassification {
  const stateReasons: string[] = [];
  
  // Handle unavailable confidence
  if (confidence === null) {
    stateReasons.push('Confidence unavailable');
    return {
      state: EdgeState.NO_ACTION,
      side: null,
      magnitude: totalDeviation,
      probability: 0.5,
      confidence: null,
      confidenceComponents: null,
      reason: 'Model data incomplete — confidence unavailable',
      actionable: false,
      showBanner: false,
      telegramEligible: false,
      stateReasons
    };
  }
  
  // No significant deviation
  if (totalDeviation < 2.0) {
    stateReasons.push(`Total deviation too small (${totalDeviation.toFixed(1)} pts)`);
    return {
      state: EdgeState.NO_ACTION,
      side: null,
      magnitude: totalDeviation,
      probability: 0.5,
      confidence,
      confidenceComponents: null,
      reason: `Model projects within statistical noise (Δ ${totalDeviation.toFixed(1)} pts)`,
      actionable: false,
      showBanner: false,
      telegramEligible: false,
      stateReasons
    };
  }
  
  // Determine side
  const side = overProb > 55 ? 'OVER' : underProb > 55 ? 'UNDER' : null;
  const sideProb = side === 'OVER' ? overProb : underProb;
  
  if (!side) {
    stateReasons.push('No directional edge (probs near 50%)');
    return {
      state: EdgeState.NO_ACTION,
      side: null,
      magnitude: totalDeviation,
      probability: 0.5,
      confidence,
      confidenceComponents: null,
      reason: 'Probabilities near 50% — no directional edge',
      actionable: false,
      showBanner: false,
      telegramEligible: false,
      stateReasons
    };
  }
  
  // Apply hysteresis
  let effectivePromoteThreshold = EDGE_PROMOTE_THRESHOLD;
  let effectiveConfidencePromote = CONFIDENCE_PROMOTE_THRESHOLD;
  
  if (previousState === EdgeState.OFFICIAL_EDGE) {
    effectivePromoteThreshold = EDGE_DEMOTE_THRESHOLD;
    effectiveConfidencePromote = CONFIDENCE_DEMOTE_THRESHOLD;
  }
  
  // Risk control checks
  const blockedByConfidence = confidence < 25;
  const blockedByVolatility = volatility > 300 && confidence < 70;
  const blockedByEV = expectedValue <= 0;
  
  // NO_ACTION
  if (blockedByConfidence || (blockedByVolatility && blockedByEV)) {
    stateReasons.push(`Blocked: confidence=${confidence}%, volatility=${volatility.toFixed(0)}, EV=${expectedValue.toFixed(2)}%`);
    return {
      state: EdgeState.NO_ACTION,
      side,
      magnitude: totalDeviation,
      probability: sideProb / 100,
      confidence,
      confidenceComponents: null,
      reason: 'Model signal blocked by risk controls',
      actionable: false,
      showBanner: false,
      telegramEligible: false,
      stateReasons
    };
  }
  
  // MODEL_LEAN
  const isLean = confidence < effectiveConfidencePromote || blockedByVolatility || blockedByEV;
  if (isLean) {
    if (confidence < effectiveConfidencePromote) stateReasons.push(`Confidence in LEAN range (${confidence}%)`);
    if (blockedByVolatility) stateReasons.push(`High volatility (σ=${volatility.toFixed(0)})`);
    if (blockedByEV) stateReasons.push(`Negative EV (${expectedValue.toFixed(2)}%)`);
    
    return {
      state: EdgeState.MODEL_LEAN,
      side,
      magnitude: totalDeviation,
      probability: sideProb / 100,
      confidence,
      confidenceComponents: null,
      reason: `Model lean: ${side} ${totalDeviation.toFixed(1)} pts, ${sideProb.toFixed(0)}% prob — not an official play`,
      actionable: false,
      showBanner: false,
      telegramEligible: false,
      stateReasons
    };
  }
  
  // OFFICIAL_EDGE
  if (totalDeviation >= effectivePromoteThreshold && confidence >= effectiveConfidencePromote && expectedValue > 0) {
    stateReasons.push(`All thresholds met: edge=${totalDeviation.toFixed(1)}, conf=${confidence}%, EV=+${expectedValue.toFixed(2)}%`);
    return {
      state: EdgeState.OFFICIAL_EDGE,
      side,
      magnitude: totalDeviation,
      probability: sideProb / 100,
      confidence,
      confidenceComponents: null,
      reason: `Official edge: ${side} ${totalDeviation.toFixed(1)} pt, ${sideProb.toFixed(0)}% prob, +${expectedValue.toFixed(1)}% EV`,
      actionable: true,
      showBanner: true,
      telegramEligible: true,
      stateReasons
    };
  }
  
  // Default MODEL_LEAN
  stateReasons.push('Edge in buffer zone');
  return {
    state: EdgeState.MODEL_LEAN,
    side,
    magnitude: totalDeviation,
    probability: sideProb / 100,
    confidence,
    confidenceComponents: null,
    reason: `Model signal detected — informational only`,
    actionable: false,
    showBanner: false,
    telegramEligible: false,
    stateReasons
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
    case EdgeState.OFFICIAL_EDGE:
      return {
        borderColor: 'border-neon-green',
        bgColor: 'bg-neon-green/10',
        textColor: 'text-neon-green',
        icon: '✅',
        label: 'OFFICIAL EDGE'
      };
    
    case EdgeState.MODEL_LEAN:
      return {
        borderColor: 'border-vibrant-yellow',
        bgColor: 'bg-vibrant-yellow/10',
        textColor: 'text-vibrant-yellow',
        icon: '⚠️',
        label: 'MODEL LEAN'
      };
    
    case EdgeState.NO_ACTION:
      return {
        borderColor: 'border-gray-600',
        bgColor: 'bg-gray-600/5',
        textColor: 'text-gray-400',
        icon: '⛔',
        label: 'NO ACTION'
      };
  }
}

/**
 * Should display side highlight (colored pill/badge)?
 * 
 * RULE: Only highlight if OFFICIAL_EDGE
 */
export function shouldHighlightSide(classification: EdgeClassification): boolean {
  return classification.state === EdgeState.OFFICIAL_EDGE && classification.side !== null;
}

/**
 * Should display raw metrics (edge pts, probability)?
 * 
 * RULE: Hide/de-emphasize for NO_ACTION and MODEL_LEAN
 * Show "Model Signal Detected — Blocked by Risk Controls" instead
 */
export function shouldShowRawMetrics(classification: EdgeClassification): boolean {
  return classification.state === EdgeState.OFFICIAL_EDGE;
}

/**
 * Get message for blocked/lean signals
 */
export function getSignalMessage(classification: EdgeClassification): string {
  if (classification.state === EdgeState.OFFICIAL_EDGE) {
    return classification.reason;
  }
  
  if (classification.state === EdgeState.MODEL_LEAN) {
    return `⚠️ Model Lean — Not an official play. ${classification.reason}`;
  }
  
  // NO_ACTION
  return classification.side 
    ? '📊 Model Signal Detected — Blocked by Risk Controls'
    : 'No actionable signal';
}

/**
 * Get Telegram posting eligibility
 */
export function getTelegramPostType(classification: EdgeClassification): 'play' | 'lean' | 'none' {
  if (classification.state === EdgeState.OFFICIAL_EDGE && classification.telegramEligible) {
    return 'play';
  }
  if (classification.state === EdgeState.MODEL_LEAN) {
    return 'lean';  // Can post as "Model Lean — Not official"
  }
  return 'none';
}

/**
 * GLOBAL DISCLAIMER - Add everywhere (UI + Telegram bio)
 */
export const PLATFORM_DISCLAIMER = 
  'BeatVegas surfaces model signals, but only releases trades that pass risk-adjusted execution thresholds.';

