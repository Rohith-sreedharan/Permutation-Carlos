/**
 * LOCKED TIER SYSTEM v1.0 — Frontend Implementation
 * ==================================================
 * Single source of truth for tier classification and display.
 * 
 * 🚨 LOCKED: Do NOT modify thresholds without explicit approval.
 * 
 * TIERS:
 * - EDGE (Tier A): Actionable bet. Telegram: PLAY
 * - LEAN (Tier B): Directional value, one+ gate fails. Telegram: LIVE WATCH
 * - NEUTRAL (Tier C): No mispricing. Telegram: NO PLAY
 * 
 * BLOCKED is NOT a tier — it's a reason code that downgrades EDGE → LEAN
 */

// =============================================================================
// LOCKED THRESHOLDS
// =============================================================================

export const LOCKED_THRESHOLDS = {
  // EDGE (Tier A) - Must pass ALL
  EDGE_MIN_PTS: 6.0,           // Minimum edge points for EDGE
  EDGE_MIN_WINPROB: 0.60,      // 60% win probability
  EDGE_MIN_STABILITY: 70,       // Stability score minimum
  
  // LEAN (Tier B) - Value threshold
  LEAN_MIN_PTS: 2.5,           // Minimum edge for LEAN
  
  // Confidence calculation
  VAR_OK: 150,                 // Variance below = no penalty
  VAR_BAD: 400,                // Variance above = max penalty
  STABILITY_MIN: 70,           // Below = penalty
  
  // Penalties
  INJURY_UNCERTAINTY_PENALTY: 20,
  MARKET_DISAGREEMENT_PENALTY: 10,
} as const;

// =============================================================================
// TYPES
// =============================================================================

export type Tier = 'EDGE' | 'LEAN' | 'NEUTRAL';
export type TelegramPostType = 'PLAY' | 'LIVE_WATCH' | 'NO_PLAY';
export type SizingTag = 'standard' | 'reduced' | 'small' | 'wait';
export type ConfidenceLabel = 'High' | 'Medium' | 'Low' | 'N/A';

export type ReasonCode =
  // EDGE reasons
  | 'all_gates_pass'
  | 'strong_edge'
  | 'high_confidence'
  // Block/downgrade reasons
  | 'high_variance'
  | 'low_stability'
  | 'ev_not_proven'
  | 'injury_uncertainty'
  | 'late_scratches_risk'
  | 'incomplete_data'
  // LEAN reasons
  | 'value_detected'
  | 'one_gate_failed'
  | 'multiple_gates_failed'
  // NEUTRAL reasons
  | 'no_mispricing'
  | 'market_aligned'
  | 'edge_below_threshold'
  // Confidence reasons
  | 'missing_inputs'
  | 'variance_penalty'
  | 'stability_penalty';

export interface ConfidenceResult {
  confidence_score: number | null;  // 0-100, NULL if inputs missing (NEVER 1%)
  confidence_label: ConfidenceLabel;
  confidence_reason_codes: ReasonCode[];
  confidence_inputs: {
    variance: number | null;
    stability_score: number | null;
    injury_uncertainty: boolean;
    market_disagreement: boolean;
  };
}

export interface EntryPlan {
  playable_at: number;
  strong_value_at: number;
  invalidate_below: number;
  current_edge_pts: number;
  instructions: string;
}

export interface TierClassification {
  tier: Tier;
  raw_tier: Tier;
  telegram_post_type: TelegramPostType;
  edge_pts: number;
  win_prob: number;
  market_line: number;
  model_fair_line: number;
  confidence: ConfidenceResult;
  gates_passed: string[];
  gates_failed: string[];
  risk_blocked: boolean;
  risk_reason_codes: ReasonCode[];
  sizing_tag: SizingTag;
  sizing_reason: string;
  entry_plan: EntryPlan | null;
  reason_codes: ReasonCode[];
  state_reasons: string[];
}

export interface SimulationSnapshot {
  snapshot_id: string;
  seed: number;
  inputs_hash: string;
  injury_inputs_hash: string;
  market_line_at_snapshot: number;
  n_sims: number;
  timestamp: string;
  edge_pts: number;
  win_prob: number;
  variance: number;
  stability_score: number;
  tier: Tier;
  confidence_score: number | null;
}

export interface SnapshotComparison {
  snapshot_id: string;
  market_line_at_snapshot: number;
  current_market_line: number;
  line_moved: number;
  injury_hash_changed: boolean;
  snapshot_still_valid: boolean;
  invalidation_reason: string | null;
}

// =============================================================================
// CONFIDENCE CALCULATION
// =============================================================================

/**
 * Calculate confidence score using penalty system
 * 
 * 🚨 RULE: If ANY input missing → return NULL, label "N/A" (NOT 1%)
 */
export function calculateConfidence(
  variance: number | null,
  stabilityScore: number | null,
  injuryUncertainty: boolean = false,
  marketDisagreement: boolean = false
): ConfidenceResult {
  const inputs = {
    variance,
    stability_score: stabilityScore,
    injury_uncertainty: injuryUncertainty,
    market_disagreement: marketDisagreement,
  };
  
  const reasonCodes: ReasonCode[] = [];
  
  // Check for missing inputs — NEVER default to 1%
  if (variance === null || stabilityScore === null) {
    return {
      confidence_score: null,  // NOT 1%!
      confidence_label: 'N/A',
      confidence_reason_codes: ['missing_inputs'],
      confidence_inputs: inputs,
    };
  }
  
  // Start at 100
  let score = 100;
  
  // Variance penalty (0-40 pts)
  if (variance > LOCKED_THRESHOLDS.VAR_OK) {
    const penVar = Math.min(40, (
      (variance - LOCKED_THRESHOLDS.VAR_OK) /
      (LOCKED_THRESHOLDS.VAR_BAD - LOCKED_THRESHOLDS.VAR_OK) * 40
    ));
    score -= penVar;
    if (penVar > 10) {
      reasonCodes.push('variance_penalty');
    }
  }
  
  // Stability penalty (0-40 pts)
  if (stabilityScore < LOCKED_THRESHOLDS.STABILITY_MIN) {
    const penStab = Math.min(40, (
      (LOCKED_THRESHOLDS.STABILITY_MIN - stabilityScore) /
      LOCKED_THRESHOLDS.STABILITY_MIN * 40
    ));
    score -= penStab;
    if (penStab > 10) {
      reasonCodes.push('stability_penalty');
    }
  }
  
  // Injury uncertainty penalty
  if (injuryUncertainty) {
    score -= LOCKED_THRESHOLDS.INJURY_UNCERTAINTY_PENALTY;
    reasonCodes.push('injury_uncertainty');
  }
  
  // Market disagreement penalty
  if (marketDisagreement) {
    score -= LOCKED_THRESHOLDS.MARKET_DISAGREEMENT_PENALTY;
  }
  
  // Clamp to 0-100
  const finalScore = Math.max(0, Math.min(100, Math.round(score)));
  
  // Determine label
  let label: ConfidenceLabel;
  if (finalScore >= 70) {
    label = 'High';
  } else if (finalScore >= 50) {
    label = 'Medium';
  } else {
    label = 'Low';
  }
  
  return {
    confidence_score: finalScore,
    confidence_label: label,
    confidence_reason_codes: reasonCodes,
    confidence_inputs: inputs,
  };
}

// =============================================================================
// TIER CLASSIFICATION
// =============================================================================

/**
 * Generate entry plan for LEAN signals
 * 
 * 🚨 LEAN must ALWAYS have entry thresholds, never "informational only"
 */
export function generateEntryPlan(marketLine: number, edgePts: number): EntryPlan {
  return {
    playable_at: marketLine,
    strong_value_at: marketLine + 1.0,
    invalidate_below: marketLine - 1.0,
    current_edge_pts: edgePts,
    instructions: `Take ${marketLine >= 0 ? '+' : ''}${marketLine.toFixed(1)} or better. Strong value at ${(marketLine + 1.0) >= 0 ? '+' : ''}${(marketLine + 1.0).toFixed(1)}+. Avoid below ${(marketLine - 1.0) >= 0 ? '+' : ''}${(marketLine - 1.0).toFixed(1)}.`,
  };
}

/**
 * LOCKED TIER CLASSIFICATION
 * 
 * Rules:
 * 1. EDGE: ALL gates pass
 * 2. LEAN: Value detected, one+ gate fails  
 * 3. NEUTRAL: No significant mispricing
 * 
 * If EDGE is blocked → downgrade to LEAN (never eliminate post)
 */
export function classifyTier(
  marketLine: number,
  modelFairLine: number,
  winProb: number,
  variance: number | null = null,
  stabilityScore: number | null = null,
  injuryImpactOk: boolean = true,
  volatilityExtreme: boolean = false,
  injuryUncertainty: boolean = false,
  marketDisagreement: boolean = false
): TierClassification {
  // Calculate edge
  const edgePts = marketLine - modelFairLine;
  
  // Calculate confidence
  const confidence = calculateConfidence(
    variance,
    stabilityScore,
    injuryUncertainty,
    marketDisagreement
  );
  
  // Track gates
  const gatesPassed: string[] = [];
  const gatesFailed: string[] = [];
  const riskReasonCodes: ReasonCode[] = [];
  const stateReasons: string[] = [];
  
  // ===================
  // GATE EVALUATION
  // ===================
  
  // Gate 1: Edge points
  if (edgePts >= LOCKED_THRESHOLDS.EDGE_MIN_PTS) {
    gatesPassed.push(`Edge ${edgePts.toFixed(1)} pts >= ${LOCKED_THRESHOLDS.EDGE_MIN_PTS}`);
  } else if (edgePts >= LOCKED_THRESHOLDS.LEAN_MIN_PTS) {
    gatesFailed.push(`Edge ${edgePts.toFixed(1)} pts < ${LOCKED_THRESHOLDS.EDGE_MIN_PTS} (LEAN range)`);
  } else {
    gatesFailed.push(`Edge ${edgePts.toFixed(1)} pts < ${LOCKED_THRESHOLDS.LEAN_MIN_PTS} (below LEAN)`);
  }
  
  // Gate 2: Win probability
  if (winProb >= LOCKED_THRESHOLDS.EDGE_MIN_WINPROB) {
    gatesPassed.push(`Win prob ${(winProb * 100).toFixed(0)}% >= ${(LOCKED_THRESHOLDS.EDGE_MIN_WINPROB * 100).toFixed(0)}%`);
  } else {
    gatesFailed.push(`Win prob ${(winProb * 100).toFixed(0)}% < ${(LOCKED_THRESHOLDS.EDGE_MIN_WINPROB * 100).toFixed(0)}%`);
  }
  
  // Gate 3: Stability
  if (stabilityScore !== null && stabilityScore >= LOCKED_THRESHOLDS.EDGE_MIN_STABILITY) {
    gatesPassed.push(`Stability ${stabilityScore.toFixed(0)} >= ${LOCKED_THRESHOLDS.EDGE_MIN_STABILITY}`);
  } else if (stabilityScore !== null) {
    gatesFailed.push(`Stability ${stabilityScore.toFixed(0)} < ${LOCKED_THRESHOLDS.EDGE_MIN_STABILITY}`);
    riskReasonCodes.push('low_stability');
  } else {
    gatesFailed.push('Stability score unavailable');
    riskReasonCodes.push('incomplete_data');
  }
  
  // Gate 4: Injury impact
  if (injuryImpactOk) {
    gatesPassed.push('Injury impact acceptable');
  } else {
    gatesFailed.push('Injury impact concern');
    riskReasonCodes.push('injury_uncertainty');
  }
  
  // Gate 5: Volatility
  if (!volatilityExtreme) {
    gatesPassed.push('Volatility not extreme');
  } else {
    gatesFailed.push('Extreme volatility');
    riskReasonCodes.push('high_variance');
  }
  
  // ===================
  // TIER DETERMINATION
  // ===================
  
  const reasonCodes: ReasonCode[] = [];
  let tier: Tier;
  let rawTier: Tier;
  let telegramPostType: TelegramPostType;
  let sizingTag: SizingTag;
  let sizingReason: string;
  let entryPlan: EntryPlan | null = null;
  
  // Check for NEUTRAL first (no value)
  if (edgePts < LOCKED_THRESHOLDS.LEAN_MIN_PTS) {
    tier = 'NEUTRAL';
    rawTier = 'NEUTRAL';
    telegramPostType = 'NO_PLAY';
    sizingTag = 'wait';
    sizingReason = 'No actionable edge';
    reasonCodes.push('no_mispricing');
    stateReasons.push(`Edge ${edgePts.toFixed(1)} pts below LEAN threshold (${LOCKED_THRESHOLDS.LEAN_MIN_PTS})`);
  }
  // Check for EDGE (all gates pass)
  else if (gatesFailed.length === 0) {
    rawTier = 'EDGE';
    const riskBlocked = riskReasonCodes.length > 0;
    
    if (riskBlocked) {
      // 🚨 CRITICAL: Downgrade to LEAN, don't eliminate
      tier = 'LEAN';
      telegramPostType = 'LIVE_WATCH';
      reasonCodes.push('one_gate_failed');
      stateReasons.push('EDGE downgraded to LEAN due to risk controls');
      entryPlan = generateEntryPlan(marketLine, edgePts);
    } else {
      tier = 'EDGE';
      telegramPostType = 'PLAY';
      reasonCodes.push('all_gates_pass');
      stateReasons.push('All gates passed — actionable EDGE');
    }
    
    // Sizing for EDGE
    if (volatilityExtreme) {
      sizingTag = 'reduced';
      sizingReason = 'High variance → ½ unit';
    } else {
      sizingTag = 'standard';
      sizingReason = 'Standard sizing';
    }
  }
  // LEAN (value detected, one+ gate fails)
  else {
    tier = 'LEAN';
    rawTier = 'LEAN';
    telegramPostType = 'LIVE_WATCH';
    sizingTag = 'small';
    sizingReason = 'LEAN signal → small size or wait';
    entryPlan = generateEntryPlan(marketLine, edgePts);
    
    if (gatesFailed.length === 1) {
      reasonCodes.push('one_gate_failed');
    } else {
      reasonCodes.push('multiple_gates_failed');
    }
    reasonCodes.push('value_detected');
    stateReasons.push(`Value detected (${edgePts.toFixed(1)} pts) but ${gatesFailed.length} gate(s) failed`);
  }
  
  return {
    tier,
    raw_tier: rawTier!,
    telegram_post_type: telegramPostType!,
    edge_pts: edgePts,
    win_prob: winProb,
    market_line: marketLine,
    model_fair_line: modelFairLine,
    confidence,
    gates_passed: gatesPassed,
    gates_failed: gatesFailed,
    risk_blocked: riskReasonCodes.length > 0,
    risk_reason_codes: riskReasonCodes,
    sizing_tag: sizingTag!,
    sizing_reason: sizingReason!,
    entry_plan: entryPlan,
    reason_codes: reasonCodes,
    state_reasons: stateReasons,
  };
}

// =============================================================================
// DISPLAY HELPERS
// =============================================================================

/**
 * Get tier display configuration
 */
export function getTierDisplay(tier: Tier): {
  label: string;
  emoji: string;
  color: string;
  bgColor: string;
  borderColor: string;
  description: string;
} {
  switch (tier) {
    case 'EDGE':
      return {
        label: 'EDGE',
        emoji: '🟢',
        color: 'text-emerald-400',
        bgColor: 'bg-emerald-500/20',
        borderColor: 'border-emerald-500',
        description: 'Actionable bet — all gates pass',
      };
    case 'LEAN':
      return {
        label: 'LEAN',
        emoji: '🟡',
        color: 'text-amber-400',
        bgColor: 'bg-amber-500/20',
        borderColor: 'border-amber-500',
        description: 'Directional value — one+ gate fails',
      };
    case 'NEUTRAL':
      return {
        label: 'NEUTRAL',
        emoji: '⚪',
        color: 'text-gray-400',
        bgColor: 'bg-gray-500/20',
        borderColor: 'border-gray-500',
        description: 'No mispricing — market aligned',
      };
  }
}

/**
 * Get confidence display configuration
 */
export function getConfidenceDisplay(confidence: ConfidenceResult): {
  label: string;
  value: string;
  color: string;
  showWarning: boolean;
  warningText: string | null;
} {
  if (confidence.confidence_score === null) {
    return {
      label: 'Confidence',
      value: 'N/A',
      color: 'text-gray-500',
      showWarning: true,
      warningText: 'Inputs missing — cannot calculate confidence',
    };
  }
  
  let color: string;
  if (confidence.confidence_score >= 70) {
    color = 'text-emerald-400';
  } else if (confidence.confidence_score >= 50) {
    color = 'text-amber-400';
  } else {
    color = 'text-red-400';
  }
  
  return {
    label: 'Confidence',
    value: `${confidence.confidence_score}% (${confidence.confidence_label})`,
    color,
    showWarning: confidence.confidence_reason_codes.length > 0,
    warningText: confidence.confidence_reason_codes.length > 0
      ? `Penalties: ${confidence.confidence_reason_codes.join(', ')}`
      : null,
  };
}

/**
 * Check if tier should generate Telegram post
 * 
 * 🚨 RULE: EDGE and LEAN both generate posts
 *          Only NEUTRAL is silent
 */
export function shouldGenerateTelegramPost(tier: Tier): boolean {
  return tier === 'EDGE' || tier === 'LEAN';
}

/**
 * Downgrade EDGE to LEAN
 * 
 * 🚨 CRITICAL: Never eliminate the post, always downgrade
 */
export function downgradeEdgeToLean(
  classification: TierClassification,
  downgradeReason: ReasonCode
): TierClassification {
  if (classification.tier !== 'EDGE') {
    return classification;
  }
  
  const entryPlan = generateEntryPlan(
    classification.market_line,
    classification.edge_pts
  );
  
  return {
    ...classification,
    tier: 'LEAN',
    telegram_post_type: 'LIVE_WATCH',
    gates_failed: [...classification.gates_failed, `Blocked: ${downgradeReason}`],
    risk_blocked: true,
    risk_reason_codes: [...classification.risk_reason_codes, downgradeReason],
    sizing_tag: 'small',
    sizing_reason: 'Downgraded from EDGE → small size',
    entry_plan: entryPlan,
    reason_codes: [...classification.reason_codes, downgradeReason],
    state_reasons: [...classification.state_reasons, `EDGE downgraded to LEAN: ${downgradeReason}`],
  };
}

// =============================================================================
// SNAPSHOT COMPARISON
// =============================================================================

/**
 * Compare current market to snapshot
 */
export function compareSnapshot(
  snapshot: SimulationSnapshot,
  currentMarketLine: number,
  currentInjuryHash: string,
  maxLineMovement: number = 2.0
): SnapshotComparison {
  const lineMoved = currentMarketLine - snapshot.market_line_at_snapshot;
  const injuryChanged = currentInjuryHash !== snapshot.injury_inputs_hash;
  
  let stillValid = true;
  let invalidationReason: string | null = null;
  
  if (Math.abs(lineMoved) > maxLineMovement) {
    stillValid = false;
    invalidationReason = `Line moved ${lineMoved >= 0 ? '+' : ''}${lineMoved.toFixed(1)} pts (threshold: ${maxLineMovement})`;
  }
  
  if (injuryChanged) {
    stillValid = false;
    invalidationReason = 'Injury inputs changed';
  }
  
  return {
    snapshot_id: snapshot.snapshot_id,
    market_line_at_snapshot: snapshot.market_line_at_snapshot,
    current_market_line: currentMarketLine,
    line_moved: lineMoved,
    injury_hash_changed: injuryChanged,
    snapshot_still_valid: stillValid,
    invalidation_reason: invalidationReason,
  };
}

/**
 * Format line movement display
 */
export function formatLineMovement(lineMoved: number): {
  text: string;
  color: string;
  emoji: string;
} {
  if (Math.abs(lineMoved) < 0.5) {
    return {
      text: 'Line stable',
      color: 'text-gray-400',
      emoji: '→',
    };
  }
  
  if (lineMoved > 0) {
    return {
      text: `Line improved +${lineMoved.toFixed(1)}`,
      color: 'text-emerald-400',
      emoji: '↑',
    };
  }
  
  return {
    text: `Line worsened ${lineMoved.toFixed(1)}`,
    color: 'text-red-400',
    emoji: '↓',
  };
}
