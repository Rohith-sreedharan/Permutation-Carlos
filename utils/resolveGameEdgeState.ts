/**
 * GAME EDGE STATE RESOLVER
 * ========================
 * 
 * Converts backend MarketView data into canonical GameEdgeState
 * 
 * RULES:
 * 1. This is the ONLY place GameEdgeState is created
 * 2. All numeric values are sanitized before inclusion
 * 3. All blocking rules are evaluated
 * 4. Market contexts are strictly isolated
 * 5. Classification is derived, not passed through
 * 6. Render flags are computed from state, not independently
 */

import type { MonteCarloSimulation, MarketView } from '../types';
import {
  GameEdgeState,
  SpreadEdgeContext,
  TotalEdgeContext,
  MoneylineEdgeContext,
  ValidatorStatus,
  ReleaseStatus,
  Classification,
  OfficialMarket,
  OfficialAction,
  Grade,
  BlockingRuleResult,
  sanitizeConfidence,
  sanitizeProbability,
  sanitizeEV,
  sanitizeCLV,
  sanitizeVolatility,
  evaluateSpreadBlockingRules,
  evaluateTotalBlockingRules,
  deriveRenderFlags,
  runPreRenderAssertions,
  generateActionSummary,
  generateEdgeExplanation,
  generateCLVNarrative,
  generateRiskControlSummary,
  isGradePublishable,
  RESOLVER_VERSION,
  UI_CONTRACT_VERSION,
} from './canonicalEdge';

// ===== CONTEXT BUILDERS =====

/**
 * Build SpreadEdgeContext from MarketView
 * Market-isolated - only reads spread data
 */
function buildSpreadContext(
  spreadView: MarketView | null | undefined,
  homeTeam: string,
  awayTeam: string,
  rawConfidence: number,
  rawVolatility: number
): SpreadEdgeContext {
  // Default empty context
  const emptyContext: SpreadEdgeContext = {
    team: null,
    team_id: null,
    side: null,
    market_line: null,
    model_line: null,
    edge_gap: 0,
    cover_probability_home: 50,
    cover_probability_away: 50,
    grade: null,
    ev: 0,
    clv: 0,
    volatility_score: 0,
    confidence_score: 0,
    risk_control_log: [],
    blocking_result: { all_passed: false, failed_blocking_rules: [], passed_blocking_rules: [] },
  };
  
  if (!spreadView) return emptyContext;
  
  // Extract selections
  const homeSelection = spreadView.selections?.find(s => s.side === 'HOME');
  const awaySelection = spreadView.selections?.find(s => s.side === 'AWAY');
  const preferredId = spreadView.model_preference_selection_id;
  const preferredSel = preferredId && preferredId !== 'NO_EDGE' && preferredId !== 'INVALID'
    ? spreadView.selections?.find(s => s.selection_id === preferredId)
    : null;
  
  // Sanitize probabilities
  const homeProb = sanitizeProbability(
    homeSelection?.model_probability ? homeSelection.model_probability * 100 : 50
  );
  const awayProb = sanitizeProbability(
    awaySelection?.model_probability ? awaySelection.model_probability * 100 : 50
  );
  
  // Sanitize confidence and volatility
  const confidence = sanitizeConfidence(rawConfidence);
  const volatility = sanitizeVolatility(rawVolatility);
  
  // Determine team and side
  let team: string | null = null;
  let side: 'HOME' | 'AWAY' | null = null;
  if (preferredSel) {
    side = preferredSel.side as 'HOME' | 'AWAY';
    team = side === 'HOME' ? homeTeam : awayTeam;
  }
  
  // Calculate edge gap
  const edgeGap = Math.abs(spreadView.edge_points || 0);
  
  // Map grade
  let grade: Grade | null = null;
  if (spreadView.grade) {
    grade = spreadView.grade as Grade;
  }
  
  // Calculate EV (simplified - should come from backend)
  const modelProb = preferredSel?.model_probability ?? 0.5;
  const marketProb = preferredSel?.market_probability ?? 0.5;
  const evCalc = (modelProb - marketProb) * 100;
  const ev = sanitizeEV(evCalc);
  
  // CLV (should come from backend, use 0 as default)
  const clv = sanitizeCLV(0);
  
  const ctx: SpreadEdgeContext = {
    team,
    team_id: null, // TODO: Populate from backend team_id
    side,
    market_line: preferredSel?.market_line_for_selection ?? null,
    model_line: preferredSel?.model_fair_line_for_selection ?? null,
    edge_gap: edgeGap,
    cover_probability_home: homeProb.valid ? homeProb.value! : 50,
    cover_probability_away: awayProb.valid ? awayProb.value! : 50,
    grade,
    ev: ev.valid ? ev.value! : 0,
    clv: clv.valid ? clv.value! : 0,
    volatility_score: volatility.valid ? volatility.value! : 0,
    confidence_score: confidence.valid ? confidence.value! : 0,
    risk_control_log: [],
    blocking_result: { all_passed: false, failed_blocking_rules: [], passed_blocking_rules: [] },
  };
  
  // Evaluate blocking rules
  ctx.blocking_result = evaluateSpreadBlockingRules(ctx);
  
  // Populate risk control log from failed rules
  ctx.risk_control_log = ctx.blocking_result.failed_blocking_rules.map(r => r.reason || r.rule_name);
  
  return ctx;
}

/**
 * Build TotalEdgeContext from MarketView
 * Market-isolated - only reads total data
 */
function buildTotalContext(
  totalView: MarketView | null | undefined,
  rawConfidence: number,
  rawVolatility: number
): TotalEdgeContext {
  // Default empty context
  const emptyContext: TotalEdgeContext = {
    side: null,
    market_total: null,
    model_total: null,
    edge_gap: 0,
    over_probability: 50,
    under_probability: 50,
    grade: null,
    ev: 0,
    clv: 0,
    volatility_score: 0,
    confidence_score: 0,
    risk_control_log: [],
    blocking_result: { all_passed: false, failed_blocking_rules: [], passed_blocking_rules: [] },
  };
  
  if (!totalView) return emptyContext;
  
  // Extract selections
  const overSelection = totalView.selections?.find(s => s.side === 'OVER');
  const underSelection = totalView.selections?.find(s => s.side === 'UNDER');
  const preferredId = totalView.model_preference_selection_id;
  const preferredSel = preferredId && preferredId !== 'NO_EDGE' && preferredId !== 'INVALID'
    ? totalView.selections?.find(s => s.selection_id === preferredId)
    : null;
  
  // Sanitize probabilities
  const overProb = sanitizeProbability(
    overSelection?.model_probability ? overSelection.model_probability * 100 : 50
  );
  const underProb = sanitizeProbability(
    underSelection?.model_probability ? underSelection.model_probability * 100 : 50
  );
  
  // Sanitize confidence and volatility
  const confidence = sanitizeConfidence(rawConfidence);
  const volatility = sanitizeVolatility(rawVolatility);
  
  // Determine side
  let side: 'OVER' | 'UNDER' | null = null;
  if (preferredSel) {
    side = preferredSel.side as 'OVER' | 'UNDER';
  }
  
  // Calculate edge gap
  const edgeGap = Math.abs(totalView.edge_points || 0);
  
  // Map grade
  let grade: Grade | null = null;
  if (totalView.grade) {
    grade = totalView.grade as Grade;
  }
  
  // Calculate EV
  const modelProb = preferredSel?.model_probability ?? 0.5;
  const marketProb = preferredSel?.market_probability ?? 0.5;
  const evCalc = (modelProb - marketProb) * 100;
  const ev = sanitizeEV(evCalc);
  
  const clv = sanitizeCLV(0);
  
  const ctx: TotalEdgeContext = {
    side,
    market_total: overSelection?.market_line_for_selection ?? null,
    model_total: preferredSel?.model_fair_line_for_selection ?? null,
    edge_gap: edgeGap,
    over_probability: overProb.valid ? overProb.value! : 50,
    under_probability: underProb.valid ? underProb.value! : 50,
    grade,
    ev: ev.valid ? ev.value! : 0,
    clv: clv.valid ? clv.value! : 0,
    volatility_score: volatility.valid ? volatility.value! : 0,
    confidence_score: confidence.valid ? confidence.value! : 0,
    risk_control_log: [],
    blocking_result: { all_passed: false, failed_blocking_rules: [], passed_blocking_rules: [] },
  };
  
  // Evaluate blocking rules
  ctx.blocking_result = evaluateTotalBlockingRules(ctx);
  
  // Populate risk control log
  ctx.risk_control_log = ctx.blocking_result.failed_blocking_rules.map(r => r.reason || r.rule_name);
  
  return ctx;
}

/**
 * Build MoneylineEdgeContext from MarketView
 * Market-isolated - only reads moneyline data
 */
function buildMoneylineContext(
  mlView: MarketView | null | undefined,
  homeTeam: string,
  awayTeam: string,
  rawConfidence: number,
  rawVolatility: number
): MoneylineEdgeContext {
  const emptyContext: MoneylineEdgeContext = {
    team: null,
    team_id: null,
    side: null,
    market_price: null,
    model_price: null,
    edge_gap: 0,
    win_probability_home: 50,
    win_probability_away: 50,
    grade: null,
    ev: 0,
    clv: 0,
    volatility_score: 0,
    confidence_score: 0,
    risk_control_log: [],
    blocking_result: { all_passed: false, failed_blocking_rules: [], passed_blocking_rules: [] },
  };
  
  if (!mlView) return emptyContext;
  
  // Minimal moneyline context for now
  const confidence = sanitizeConfidence(rawConfidence);
  const volatility = sanitizeVolatility(rawVolatility);
  
  return {
    ...emptyContext,
    confidence_score: confidence.valid ? confidence.value! : 0,
    volatility_score: volatility.valid ? volatility.value! : 0,
  };
}

// ===== CLASSIFICATION DERIVATION =====

/**
 * Derive classification from market contexts
 * Classification is COMPUTED, not passed through
 */
function deriveClassification(
  spreadCtx: SpreadEdgeContext,
  totalCtx: TotalEdgeContext,
  spreadView: MarketView | null | undefined,
  totalView: MarketView | null | undefined
): Classification {
  // Check if any market has a valid edge
  const spreadHasEdge = spreadCtx.blocking_result.all_passed && 
    spreadView?.edge_class === 'EDGE' &&
    isGradePublishable(spreadCtx.grade);
    
  const totalHasEdge = totalCtx.blocking_result.all_passed && 
    totalView?.edge_class === 'EDGE' &&
    isGradePublishable(totalCtx.grade);
  
  const spreadHasLean = spreadView?.edge_class === 'LEAN' &&
    spreadCtx.confidence_score >= 25;
    
  const totalHasLean = totalView?.edge_class === 'LEAN' &&
    totalCtx.confidence_score >= 25;
  
  // Priority: EDGE > LEAN > MARKET_ALIGNED > NO_ACTION
  if (spreadHasEdge || totalHasEdge) {
    return Classification.EDGE;
  }
  
  if (spreadHasLean || totalHasLean) {
    return Classification.LEAN;
  }
  
  // Check if blocked
  const spreadBlocked = !spreadCtx.blocking_result.all_passed && 
    spreadCtx.blocking_result.failed_blocking_rules.length > 0;
  const totalBlocked = !totalCtx.blocking_result.all_passed && 
    totalCtx.blocking_result.failed_blocking_rules.length > 0;
  
  if (spreadBlocked && totalBlocked) {
    return Classification.NO_ACTION;
  }
  
  return Classification.MARKET_ALIGNED;
}

/**
 * Derive release status from blocking rules
 */
function deriveReleaseStatus(
  spreadCtx: SpreadEdgeContext,
  totalCtx: TotalEdgeContext,
  classification: Classification
): ReleaseStatus {
  if (classification === Classification.EDGE && 
      (spreadCtx.blocking_result.all_passed || totalCtx.blocking_result.all_passed)) {
    return ReleaseStatus.APPROVED;
  }
  
  // Find first blocker
  const allFailed = [
    ...spreadCtx.blocking_result.failed_blocking_rules,
    ...totalCtx.blocking_result.failed_blocking_rules,
  ];
  
  if (allFailed.length === 0 && classification === Classification.LEAN) {
    return ReleaseStatus.APPROVED;
  }
  
  const firstFailed = allFailed[0];
  if (!firstFailed) {
    return ReleaseStatus.PENDING_REVIEW;
  }
  
  switch (firstFailed.rule_id) {
    case 'EV_POSITIVE':
      return ReleaseStatus.BLOCKED_BY_EV;
    case 'MIN_GAP':
      return ReleaseStatus.BLOCKED_BY_GAP;
    case 'VOLATILITY':
      return ReleaseStatus.BLOCKED_BY_VOLATILITY;
    case 'GRADE_GATE':
      return ReleaseStatus.BLOCKED_BY_GRADE;
    default:
      return ReleaseStatus.BLOCKED_BY_INTEGRITY;
  }
}

/**
 * Derive official market, side, and action
 */
function deriveOfficialPlay(
  spreadCtx: SpreadEdgeContext,
  totalCtx: TotalEdgeContext,
  classification: Classification
): { market: OfficialMarket | null; side: string | null; action: OfficialAction } {
  if (classification !== Classification.EDGE && classification !== Classification.LEAN) {
    return { market: null, side: null, action: OfficialAction.NO_ACTION };
  }
  
  // Prefer spread edge over total
  if (spreadCtx.blocking_result.all_passed && spreadCtx.team && spreadCtx.side) {
    const isUnderdog = spreadCtx.market_line !== null && spreadCtx.market_line > 0;
    return {
      market: OfficialMarket.SPREAD,
      side: spreadCtx.team,
      action: isUnderdog ? OfficialAction.TAKE_POINTS : OfficialAction.LAY_POINTS,
    };
  }
  
  if (totalCtx.blocking_result.all_passed && totalCtx.side) {
    return {
      market: OfficialMarket.TOTAL,
      side: totalCtx.side,
      action: totalCtx.side === 'OVER' ? OfficialAction.OVER : OfficialAction.UNDER,
    };
  }
  
  return { market: null, side: null, action: OfficialAction.NO_ACTION };
}

// ===== MAIN RESOLVER =====

/**
 * Resolve GameEdgeState from simulation data
 * 
 * This is the ONLY entry point for creating canonical state.
 * All UI components must use this resolved state.
 */
export function resolveGameEdgeState(
  simulation: MonteCarloSimulation | null | undefined,
  eventId: string,
  homeTeam: string,
  awayTeam: string
): GameEdgeState | null {
  if (!simulation) return null;
  
  const marketViews = simulation.market_views;
  const snapshotHash = marketViews?.spread?.snapshot_hash || 
                       marketViews?.total?.snapshot_hash || 
                       `sim-${Date.now()}`;
  
  // Extract raw values for sanitization
  const rawConfidence = (simulation.confidence_score || 0.5) * 100;
  const rawVolatilityRaw = simulation.volatility_score || simulation.volatility_index || 100;
  const rawVolatility = Number(rawVolatilityRaw);
  
  // Build market-isolated contexts
  const spreadCtx = buildSpreadContext(
    marketViews?.spread,
    homeTeam,
    awayTeam,
    rawConfidence,
    rawVolatility
  );
  
  const totalCtx = buildTotalContext(
    marketViews?.total,
    rawConfidence,
    rawVolatility
  );
  
  const mlCtx = buildMoneylineContext(
    marketViews?.moneyline,
    homeTeam,
    awayTeam,
    rawConfidence,
    rawVolatility
  );
  
  // Derive classification (not passed through)
  const classification = deriveClassification(
    spreadCtx,
    totalCtx,
    marketViews?.spread,
    marketViews?.total
  );
  
  // Derive release status
  const releaseStatus = deriveReleaseStatus(spreadCtx, totalCtx, classification);
  
  // Derive official play
  const { market, side, action } = deriveOfficialPlay(spreadCtx, totalCtx, classification);
  
  // Count rules
  const totalRules = spreadCtx.blocking_result.passed_blocking_rules.length + 
                     spreadCtx.blocking_result.failed_blocking_rules.length +
                     totalCtx.blocking_result.passed_blocking_rules.length +
                     totalCtx.blocking_result.failed_blocking_rules.length;
  const passedRules = spreadCtx.blocking_result.passed_blocking_rules.length +
                      totalCtx.blocking_result.passed_blocking_rules.length;
  
  // Collect failed rules
  const failedBlocking = [
    ...spreadCtx.blocking_result.failed_blocking_rules.map(r => r.reason || r.rule_name),
    ...totalCtx.blocking_result.failed_blocking_rules.map(r => r.reason || r.rule_name),
  ];
  
  // Determine validator status
  const validatorStatus = marketViews?.spread?.integrity_status === 'PASS' ||
                          marketViews?.total?.integrity_status === 'PASS'
    ? ValidatorStatus.PASS
    : marketViews?.spread?.integrity_status === 'FAIL' ||
      marketViews?.total?.integrity_status === 'FAIL'
    ? ValidatorStatus.FAIL
    : ValidatorStatus.DEGRADED;
  
  // Build partial state for render flag derivation
  const partialState: Partial<GameEdgeState> = {
    classification,
    release_status: releaseStatus,
    spread_context: spreadCtx,
    total_context: totalCtx,
  };
  
  // Derive render flags
  const renderFlags = deriveRenderFlags(partialState);
  
  // Build full state
  const state: GameEdgeState = {
    event_id: eventId,
    snapshot_hash: snapshotHash,
    snapshot_timestamp: new Date().toISOString(),
    resolver_version: RESOLVER_VERSION,
    ui_contract_version: UI_CONTRACT_VERSION,
    validator_status: validatorStatus,
    release_status: releaseStatus,
    classification,
    official_market: market,
    official_side: side,
    official_action: action,
    rules_passed: passedRules,
    rules_total: totalRules,
    failed_blocking_rules: failedBlocking,
    failed_scoring_rules: [],
    spread_context: spreadCtx,
    total_context: totalCtx,
    moneyline_context: mlCtx,
    render_flags: renderFlags,
    assertion_result: { all_passed: true, assertions: [] }, // Will be populated
    narrative: {
      edge_explanation: '',
      action_summary: '',
      clv_text: '',
      risk_control_summary: '',
    },
  };
  
  // Run pre-render assertions
  state.assertion_result = runPreRenderAssertions(state);
  
  // Generate narratives from state (data-driven)
  state.narrative = {
    edge_explanation: generateEdgeExplanation(state),
    action_summary: generateActionSummary(state),
    clv_text: generateCLVNarrative(spreadCtx.clv || totalCtx.clv || 0),
    risk_control_summary: generateRiskControlSummary(state),
  };
  
  return state;
}

/**
 * Check if a resolved state can be published
 */
export function canPublish(state: GameEdgeState | null): boolean {
  if (!state) return false;
  return state.assertion_result.all_passed;
}

/**
 * Get failure reasons from a resolved state
 */
export function getFailureReasons(state: GameEdgeState | null): string[] {
  if (!state) return ['No state resolved'];
  
  const reasons: string[] = [];
  
  if (!state.assertion_result.all_passed) {
    state.assertion_result.assertions
      .filter(a => !a.passed)
      .forEach(a => reasons.push(a.message));
  }
  
  reasons.push(...state.failed_blocking_rules);
  
  return reasons;
}
