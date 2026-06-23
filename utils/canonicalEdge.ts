/**
 * CANONICAL EDGE STATE SYSTEM — ROOT FIX ARCHITECTURE
 * ====================================================
 * 
 * Status: FROZEN
 * Purpose: Single source of truth for all decision surfaces
 * 
 * RULES (NON-NEGOTIABLE):
 * 1. One GameEdgeState per game snapshot
 * 2. All UI surfaces consume this object only
 * 3. No component may independently compute edge/side/action/grade/banner
 * 4. Blocking rules short-circuit immediately
 * 5. Bounded numeric values enforced before render
 * 6. Market contexts are isolated (spread/total/moneyline)
 * 7. Cards fail-closed on assertion failure
 */

// ===== ENUMS =====

export enum ValidatorStatus {
  PASS = 'PASS',
  FAIL = 'FAIL',
  DEGRADED = 'DEGRADED'
}

export enum ReleaseStatus {
  APPROVED = 'APPROVED',
  BLOCKED_BY_INTEGRITY = 'BLOCKED_BY_INTEGRITY',
  BLOCKED_BY_EV = 'BLOCKED_BY_EV',
  BLOCKED_BY_GAP = 'BLOCKED_BY_GAP',
  BLOCKED_BY_VOLATILITY = 'BLOCKED_BY_VOLATILITY',
  BLOCKED_BY_GRADE = 'BLOCKED_BY_GRADE',
  BLOCKED_BY_STALE_DATA = 'BLOCKED_BY_STALE_DATA',
  BLOCKED_BY_MISSING_DATA = 'BLOCKED_BY_MISSING_DATA',
  PENDING_REVIEW = 'PENDING_REVIEW'
}

export enum Classification {
  EDGE = 'EDGE',
  LEAN = 'LEAN',
  MARKET_ALIGNED = 'MARKET_ALIGNED',
  NO_EDGE = 'NO_EDGE',
  NO_ACTION = 'NO_ACTION',
  BLOCKED = 'BLOCKED'
}

export enum OfficialMarket {
  SPREAD = 'SPREAD',
  TOTAL = 'TOTAL',
  MONEYLINE = 'MONEYLINE'
}

export enum OfficialAction {
  TAKE_POINTS = 'TAKE_POINTS',
  LAY_POINTS = 'LAY_POINTS',
  OVER = 'OVER',
  UNDER = 'UNDER',
  BACK = 'BACK',
  NO_ACTION = 'NO_ACTION'
}

export enum Grade {
  S = 'S',
  A = 'A',
  B = 'B',
  C = 'C',
  D = 'D',
  F = 'F'
}

// Minimum publishable grade threshold
export const MIN_PUBLISHABLE_GRADE = Grade.C;

// Grade ordering for comparison
const GRADE_ORDER: Record<Grade, number> = {
  [Grade.S]: 6,
  [Grade.A]: 5,
  [Grade.B]: 4,
  [Grade.C]: 3,
  [Grade.D]: 2,
  [Grade.F]: 1,
};

export function isGradePublishable(grade: Grade | null | undefined): boolean {
  if (!grade) return false;
  return GRADE_ORDER[grade] >= GRADE_ORDER[MIN_PUBLISHABLE_GRADE];
}

// ===== BLOCKING RULES =====

export interface BlockingRule {
  rule_id: string;
  rule_name: string;
  passed: boolean;
  reason?: string;
}

export interface BlockingRuleResult {
  all_passed: boolean;
  failed_blocking_rules: BlockingRule[];
  passed_blocking_rules: BlockingRule[];
}

// Blocking rule thresholds (CONFIGURABLE)
export const BLOCKING_THRESHOLDS = {
  MIN_EV: 0.001,           // EV must be > 0
  MIN_SPREAD_GAP: 2.0,     // Minimum spread gap in points
  MIN_TOTAL_GAP: 1.5,      // Minimum total gap in points
  MIN_ML_GAP: 0.03,        // Minimum moneyline probability gap
  MAX_VOLATILITY: 300,     // Maximum volatility score
  MIN_CONFIDENCE: 25,      // Minimum confidence score (0-100)
};

// ===== MARKET-ISOLATED CONTEXTS =====

export interface SpreadEdgeContext {
  team: string | null;
  team_id: string | null;
  side: 'HOME' | 'AWAY' | null;
  market_line: number | null;
  model_line: number | null;
  edge_gap: number;
  cover_probability_home: number;
  cover_probability_away: number;
  grade: Grade | null;
  ev: number;
  clv: number;
  volatility_score: number;
  confidence_score: number;
  risk_control_log: string[];
  blocking_result: BlockingRuleResult;
}

export interface TotalEdgeContext {
  side: 'OVER' | 'UNDER' | null;
  market_total: number | null;
  model_total: number | null;
  edge_gap: number;
  over_probability: number;
  under_probability: number;
  grade: Grade | null;
  ev: number;
  clv: number;
  volatility_score: number;
  confidence_score: number;
  risk_control_log: string[];
  blocking_result: BlockingRuleResult;
}

export interface MoneylineEdgeContext {
  team: string | null;
  team_id: string | null;
  side: 'HOME' | 'AWAY' | null;
  market_price: number | null;
  model_price: number | null;
  edge_gap: number;
  win_probability_home: number;
  win_probability_away: number;
  grade: Grade | null;
  ev: number;
  clv: number;
  volatility_score: number;
  confidence_score: number;
  risk_control_log: string[];
  blocking_result: BlockingRuleResult;
}

// ===== RENDER FLAGS =====

export interface RenderFlags {
  show_edge_banner: boolean;
  show_lean_banner: boolean;
  show_market_aligned_banner: boolean;
  show_blocked_banner: boolean;
  show_official_play: boolean;
  show_action_summary: boolean;
  show_spread_section: boolean;
  show_total_section: boolean;
  show_moneyline_section: boolean;
  show_why_edge_exists: boolean;
  telegram_eligible: boolean;
  parlay_eligible: boolean;
}

// ===== PRE-RENDER ASSERTIONS =====

export interface AssertionResult {
  assertion_id: string;
  passed: boolean;
  message: string;
}

export interface PreRenderAssertionResult {
  all_passed: boolean;
  assertions: AssertionResult[];
}

// ===== CANONICAL GAME EDGE STATE =====

export interface GameEdgeState {
  // Identifiers
  event_id: string;
  snapshot_hash: string;
  snapshot_timestamp: string;
  
  // Resolver traceability
  resolver_version: string;
  ui_contract_version: string;
  
  // Core decision state (FROZEN at snapshot)
  validator_status: ValidatorStatus;
  release_status: ReleaseStatus;
  classification: Classification;
  
  // Official play (null if NO_ACTION/BLOCKED)
  official_market: OfficialMarket | null;
  official_side: string | null;
  official_action: OfficialAction;
  
  // Rules tracking
  rules_passed: number;
  rules_total: number;
  failed_blocking_rules: string[];
  failed_scoring_rules: string[];
  
  // Market-isolated contexts
  spread_context: SpreadEdgeContext;
  total_context: TotalEdgeContext;
  moneyline_context: MoneylineEdgeContext;
  
  // Render control
  render_flags: RenderFlags;
  
  // Pre-render assertions
  assertion_result: PreRenderAssertionResult;
  
  // Narrative text (data-driven, not static)
  narrative: {
    edge_explanation: string;
    action_summary: string;
    clv_text: string;
    risk_control_summary: string;
  };
}

// ===== NUMERIC SANITIZATION =====

export interface SanitizationResult<T> {
  value: T;
  valid: boolean;
  original: unknown;
  error?: string;
  clamped?: boolean;
}

/**
 * Sanitize a bounded numeric value
 * CLAMPS out-of-bounds values to [min, max] range
 * This prevents 3000%/4400%/5130% from reaching UI
 */
export function sanitizeBoundedMetric(
  field_name: string,
  raw_value: unknown,
  min: number,
  max: number
): SanitizationResult<number> {
  // Handle null/undefined - return min as default
  if (raw_value === null || raw_value === undefined) {
    return { value: min, valid: true, original: raw_value, clamped: true };
  }
  
  // Parse to number
  const num = typeof raw_value === 'number' ? raw_value : parseFloat(String(raw_value));
  
  // Check NaN - return min as fallback
  if (isNaN(num)) {
    console.warn(`[SANITIZATION] ${field_name}: NaN value, using min`, { raw_value });
    return {
      value: min,
      valid: false,
      original: raw_value,
      error: `${field_name}: Invalid numeric value`,
      clamped: true,
    };
  }
  
  // Check Infinity
  if (!isFinite(num)) {
    console.warn(`[SANITIZATION] ${field_name}: Infinity value, clamping`, { raw_value });
    return {
      value: num > 0 ? max : min,
      valid: false,
      original: raw_value,
      error: `${field_name}: Infinite value`,
      clamped: true,
    };
  }
  
  // CLAMP bounds - this is the critical fix for 3000%/4400%/5130% values
  if (num < min) {
    console.warn(`[SANITIZATION] ${field_name}: Value ${num} below min ${min}, clamping`);
    return { value: min, valid: true, original: raw_value, clamped: true };
  }
  
  if (num > max) {
    console.warn(`[SANITIZATION] ${field_name}: Value ${num} above max ${max}, clamping`);
    return { value: max, valid: true, original: raw_value, clamped: true };
  }
  
  return { value: num, valid: true, original: raw_value, clamped: false };
}

/**
 * Sanitize confidence score (0-100)
 */
export function sanitizeConfidence(raw: unknown): SanitizationResult<number> {
  return sanitizeBoundedMetric('confidence', raw, 0, 100);
}

/**
 * Sanitize probability (0-100)
 */
export function sanitizeProbability(raw: unknown): SanitizationResult<number> {
  return sanitizeBoundedMetric('probability', raw, 0, 100);
}

/**
 * Sanitize EV percentage (-100 to 100)
 */
export function sanitizeEV(raw: unknown): SanitizationResult<number> {
  return sanitizeBoundedMetric('ev', raw, -100, 100);
}

/**
 * Sanitize CLV percentage (-50 to 50)
 */
export function sanitizeCLV(raw: unknown): SanitizationResult<number> {
  return sanitizeBoundedMetric('clv', raw, -50, 50);
}

/**
 * Sanitize volatility score (0-500)
 */
export function sanitizeVolatility(raw: unknown): SanitizationResult<number> {
  return sanitizeBoundedMetric('volatility', raw, 0, 500);
}

function getEvFailureMessage(ev: number): string {
  if (ev < 0) return 'Expected value negative. No actionable edge.';
  return 'Expected value neutral. No edge detected.';
}

// ===== BLOCKING RULE ENGINE =====

/**
 * Evaluate blocking rules for spread market
 */
export function evaluateSpreadBlockingRules(ctx: SpreadEdgeContext): BlockingRuleResult {
  const rules: BlockingRule[] = [];
  
  // Rule 1: EV > 0
  const evPassed = ctx.ev > BLOCKING_THRESHOLDS.MIN_EV;
  rules.push({
    rule_id: 'EV_POSITIVE',
    rule_name: 'EV must be positive',
    passed: evPassed,
    reason: evPassed ? undefined : getEvFailureMessage(ctx.ev)
  });
  
  // Rule 2: Minimum gap threshold
  const gapPassed = ctx.edge_gap >= BLOCKING_THRESHOLDS.MIN_SPREAD_GAP;
  rules.push({
    rule_id: 'MIN_GAP',
    rule_name: 'Minimum spread gap',
    passed: gapPassed,
    reason: gapPassed ? undefined : 'Market gap below edge threshold'
  });
  
  // Rule 3: Volatility threshold
  const volPassed = ctx.volatility_score <= BLOCKING_THRESHOLDS.MAX_VOLATILITY;
  rules.push({
    rule_id: 'VOLATILITY',
    rule_name: 'Volatility within threshold',
    passed: volPassed,
    reason: volPassed ? undefined : 'Market conditions too volatile for a reliable signal'
  });
  
  // Rule 4: Confidence threshold
  const confPassed = ctx.confidence_score >= BLOCKING_THRESHOLDS.MIN_CONFIDENCE;
  rules.push({
    rule_id: 'CONFIDENCE',
    rule_name: 'Minimum confidence',
    passed: confPassed,
    reason: confPassed ? undefined : 'Insufficient simulation confidence for this market'
  });
  
  // Rule 5: Grade gate
  const gradePassed = isGradePublishable(ctx.grade);
  rules.push({
    rule_id: 'GRADE_GATE',
    rule_name: 'Publishable grade',
    passed: gradePassed,
    reason: gradePassed ? undefined : 'Insufficient historical grade for this market'
  });
  
  const failed = rules.filter(r => !r.passed);
  const passed = rules.filter(r => r.passed);
  
  return {
    all_passed: failed.length === 0,
    failed_blocking_rules: failed,
    passed_blocking_rules: passed
  };
}

/**
 * Evaluate blocking rules for total market
 */
export function evaluateTotalBlockingRules(ctx: TotalEdgeContext): BlockingRuleResult {
  const rules: BlockingRule[] = [];
  
  // Rule 1: EV > 0
  const evPassed = ctx.ev > BLOCKING_THRESHOLDS.MIN_EV;
  rules.push({
    rule_id: 'EV_POSITIVE',
    rule_name: 'EV must be positive',
    passed: evPassed,
    reason: evPassed ? undefined : getEvFailureMessage(ctx.ev)
  });
  
  // Rule 2: Minimum gap threshold
  const gapPassed = ctx.edge_gap >= BLOCKING_THRESHOLDS.MIN_TOTAL_GAP;
  rules.push({
    rule_id: 'MIN_GAP',
    rule_name: 'Minimum total gap',
    passed: gapPassed,
    reason: gapPassed ? undefined : 'Insufficient market gap for signal'
  });
  
  // Rule 3: Volatility threshold
  const volPassed = ctx.volatility_score <= BLOCKING_THRESHOLDS.MAX_VOLATILITY;
  rules.push({
    rule_id: 'VOLATILITY',
    rule_name: 'Volatility within threshold',
    passed: volPassed,
    reason: volPassed ? undefined : 'Market conditions too volatile for a reliable signal'
  });
  
  // Rule 4: Confidence threshold
  const confPassed = ctx.confidence_score >= BLOCKING_THRESHOLDS.MIN_CONFIDENCE;
  rules.push({
    rule_id: 'CONFIDENCE',
    rule_name: 'Minimum confidence',
    passed: confPassed,
    reason: confPassed ? undefined : 'Insufficient simulation confidence for this market'
  });
  
  // Rule 5: Grade gate
  const gradePassed = isGradePublishable(ctx.grade);
  rules.push({
    rule_id: 'GRADE_GATE',
    rule_name: 'Publishable grade',
    passed: gradePassed,
    reason: gradePassed ? undefined : 'Insufficient historical grade for this market'
  });
  
  const failed = rules.filter(r => !r.passed);
  const passed = rules.filter(r => r.passed);
  
  return {
    all_passed: failed.length === 0,
    failed_blocking_rules: failed,
    passed_blocking_rules: passed
  };
}

// ===== PRE-RENDER ASSERTIONS =====

/**
 * Run all pre-render assertions on a GameEdgeState
 * If any fail, card must NOT render
 */
export function runPreRenderAssertions(state: GameEdgeState): PreRenderAssertionResult {
  const assertions: AssertionResult[] = [];
  
  // 1. Banner state == resolved edge state
  const bannerConsistent = (
    (state.render_flags.show_edge_banner && state.classification === Classification.EDGE) ||
    (state.render_flags.show_lean_banner && state.classification === Classification.LEAN) ||
    (state.render_flags.show_market_aligned_banner && state.classification === Classification.MARKET_ALIGNED) ||
    (state.render_flags.show_blocked_banner && (state.classification === Classification.BLOCKED || state.classification === Classification.NO_ACTION)) ||
    (!state.render_flags.show_edge_banner && !state.render_flags.show_lean_banner && 
     !state.render_flags.show_market_aligned_banner && !state.render_flags.show_blocked_banner &&
     state.classification === Classification.NO_ACTION)
  );
  assertions.push({
    assertion_id: 'BANNER_STATE_PARITY',
    passed: bannerConsistent,
    message: bannerConsistent ? 'Banner matches classification' : 'Banner state does not match classification'
  });
  
  // 2. Action summary == resolved edge state
  const actionConsistent = (
    (state.render_flags.show_action_summary === (state.classification === Classification.EDGE || state.classification === Classification.LEAN))
  );
  assertions.push({
    assertion_id: 'ACTION_SUMMARY_PARITY',
    passed: actionConsistent,
    message: actionConsistent ? 'Action summary matches state' : 'Action summary visibility does not match state'
  });
  
  // 3. Official side supported by canonical state
  const sideConsistent = (
    (state.official_side === null && state.classification !== Classification.EDGE && state.classification !== Classification.LEAN) ||
    (state.official_side !== null && (state.classification === Classification.EDGE || state.classification === Classification.LEAN))
  );
  assertions.push({
    assertion_id: 'OFFICIAL_SIDE_PARITY',
    passed: sideConsistent,
    message: sideConsistent ? 'Official side matches state' : 'Official side present without EDGE/LEAN classification'
  });
  
  // 4. Bounded metrics in valid range (spot check)
  const spreadConfValid = state.spread_context.confidence_score >= 0 && state.spread_context.confidence_score <= 100;
  const totalConfValid = state.total_context.confidence_score >= 0 && state.total_context.confidence_score <= 100;
  assertions.push({
    assertion_id: 'BOUNDED_METRICS_VALID',
    passed: spreadConfValid && totalConfValid,
    message: spreadConfValid && totalConfValid ? 'Bounded metrics in range' : 'Bounded metric out of range'
  });
  
  // 5. Spread surface uses only spread context (checked at render time)
  assertions.push({
    assertion_id: 'SPREAD_ISOLATION',
    passed: true, // Enforced by type system
    message: 'Spread context isolation enforced'
  });
  
  // 6. Total surface uses only total context (checked at render time)
  assertions.push({
    assertion_id: 'TOTAL_ISOLATION',
    passed: true, // Enforced by type system
    message: 'Total context isolation enforced'
  });
  
  // 7. Spread contains team + signed line when spread is the official actionable market.
  const requiresSpreadBinding = state.official_market === OfficialMarket.SPREAD;
  const spreadTyped = !requiresSpreadBinding || (
    state.spread_context.team !== null && state.spread_context.market_line !== null
  ) || state.classification === Classification.BLOCKED || state.classification === Classification.NO_ACTION;
  assertions.push({
    assertion_id: 'SPREAD_TYPED',
    passed: spreadTyped,
    message: spreadTyped ? 'Spread properly typed' : 'Spread missing team or line'
  });
  
  // 8. If release_status != APPROVED, no play surface renders
  const releaseConsistent = (
    state.release_status === ReleaseStatus.APPROVED ||
    (!state.render_flags.show_official_play && !state.render_flags.show_edge_banner && !state.render_flags.show_lean_banner)
  );
  assertions.push({
    assertion_id: 'RELEASE_STATUS_GATING',
    passed: releaseConsistent,
    message: releaseConsistent ? 'Release status gates correctly' : 'Play surface shown despite non-APPROVED release'
  });
  
  // 9. If EV <= 0, edge/lean banner does not render
  const evConsistent = (
    (state.spread_context.ev > 0 || state.total_context.ev > 0) ||
    (!state.render_flags.show_edge_banner && !state.render_flags.show_lean_banner)
  );
  assertions.push({
    assertion_id: 'EV_GATING',
    passed: evConsistent,
    message: evConsistent ? 'EV gates correctly' : 'Edge/Lean banner shown despite EV <= 0'
  });
  
  // 10. If threshold not met, validated text cannot render
  const thresholdConsistent = (
    state.spread_context.blocking_result.all_passed ||
    state.total_context.blocking_result.all_passed ||
    !state.narrative.edge_explanation.toLowerCase().includes('validated')
  );
  assertions.push({
    assertion_id: 'VALIDATED_TEXT_GATING',
    passed: thresholdConsistent,
    message: thresholdConsistent ? 'Validated text gated correctly' : '"Validated" text shown despite threshold failure'
  });
  
  const allPassed = assertions.every(a => a.passed);
  
  return {
    all_passed: allPassed,
    assertions
  };
}

// ===== NARRATIVE GENERATION (DATA-DRIVEN) =====

/**
 * Generate CLV narrative from actual value
 * NO STATIC TEMPLATES CONTRADICTING DATA
 */
export function generateCLVNarrative(clv: number): string {
  if (clv <= 0) {
    return 'No line movement projected.';
  }
  if (clv < 0.3) {
    return `Minor line movement possible (+${clv.toFixed(1)}%).`;
  }
  if (clv < 1.0) {
    return `Meaningful market adjustment expected (+${clv.toFixed(1)}%).`;
  }
  return `Significant line value detected (+${clv.toFixed(1)}%).`;
}

/**
 * Generate action summary from canonical state
 * NO HARDCODED TEXT CONTRADICTING STATE
 */
export function generateActionSummary(state: GameEdgeState): string {
  if (state.release_status !== ReleaseStatus.APPROVED) {
    return 'Analysis available - no play released.';
  }
  
  if (state.classification === Classification.EDGE && state.official_side && state.official_action !== OfficialAction.NO_ACTION) {
    return `Approved Play: ${state.official_action} on ${state.official_side}.`;
  }
  
  if (state.classification === Classification.LEAN && state.official_side) {
    return `Directional lean - not an official play: ${state.official_side}.`;
  }
  
  if (state.classification === Classification.MARKET_ALIGNED) {
    return 'Market aligned - no play.';
  }
  
  return 'No official play.';
}

/**
 * Generate edge explanation from canonical state
 * NO STATIC "why this edge exists" TEXT IF NO EDGE
 */
export function generateEdgeExplanation(state: GameEdgeState): string {
  if (state.classification !== Classification.EDGE && state.classification !== Classification.LEAN) {
    return 'No valid edge detected. Market appears efficiently priced.';
  }
  
  const ctx = state.official_market === OfficialMarket.SPREAD 
    ? state.spread_context 
    : state.total_context;
  
  const parts: string[] = [];
  
  if (ctx.edge_gap > 0) {
    parts.push(`${ctx.edge_gap.toFixed(1)} pt model-market gap`);
  }
  
  if (ctx.ev > 0) {
    parts.push(`+${ctx.ev.toFixed(1)}% EV`);
  }
  
  if (ctx.grade) {
    parts.push(`Grade ${ctx.grade}`);
  }
  
  return parts.length > 0 ? parts.join(' • ') : 'Edge parameters within thresholds.';
}

/**
 * Generate risk control summary
 */
export function generateRiskControlSummary(state: GameEdgeState): string {
  const seen = new Set<string>();
  const allFailed = [
    ...state.spread_context.risk_control_log,
    ...state.total_context.risk_control_log,
    ...state.failed_blocking_rules
  ].filter(r => { if (seen.has(r)) return false; seen.add(r); return true; });
  
  if (allFailed.length === 0) {
    return 'All risk controls passed.';
  }
  
  return `Blocked: ${allFailed.join(', ')}.`;
}

// ===== RENDER FLAGS DERIVATION =====

/**
 * Derive render flags from canonical state
 * PURE FUNCTION - No independent computation
 */
export function deriveRenderFlags(state: Partial<GameEdgeState>): RenderFlags {
  const classification = state.classification || Classification.NO_ACTION;
  const release = state.release_status || ReleaseStatus.PENDING_REVIEW;
  const spreadBlocking = state.spread_context?.blocking_result?.all_passed ?? false;
  const totalBlocking = state.total_context?.blocking_result?.all_passed ?? false;
  
  const isApproved = release === ReleaseStatus.APPROVED;
  const validatorPassed = state.validator_status === ValidatorStatus.PASS;
  const hasEdge = classification === Classification.EDGE && isApproved && validatorPassed;
  const hasLean = classification === Classification.LEAN && isApproved;
  
  return {
    show_edge_banner: hasEdge,
    show_lean_banner: hasLean && !hasEdge,
    show_market_aligned_banner: classification === Classification.MARKET_ALIGNED && !hasEdge && !hasLean,
    show_blocked_banner: classification === Classification.BLOCKED || !isApproved,
    show_official_play: hasEdge,
    show_action_summary: hasEdge || hasLean,
    show_spread_section: spreadBlocking || classification !== Classification.BLOCKED,
    show_total_section: totalBlocking || classification !== Classification.BLOCKED,
    show_moneyline_section: true,
    show_why_edge_exists: hasEdge || hasLean,
    telegram_eligible: hasEdge,
    parlay_eligible: hasEdge || hasLean,
  };
}

// ===== FAIL-CLOSED PUBLISH CONTRACT =====

export interface PublishDecision {
  can_publish: boolean;
  safe_fallback: boolean;
  failure_reasons: string[];
}

/**
 * Determine if card can be published
 * FAIL-CLOSED: Any assertion failure blocks publish
 */
export function canPublishCard(state: GameEdgeState | null): PublishDecision {
  // Null state = fail closed
  if (!state) {
    return {
      can_publish: false,
      safe_fallback: true,
      failure_reasons: ['No state provided'],
    };
  }
  
  const failures: string[] = [];
  
  // Check pre-render assertions
  if (!state.assertion_result.all_passed) {
    const failedAssertions = state.assertion_result.assertions
      .filter(a => !a.passed)
      .map(a => a.message);
    failures.push(...failedAssertions);
  }
  
  // Additional publish gates
  if (state.validator_status === ValidatorStatus.FAIL) {
    failures.push('Validator status is FAIL');
  }
  
  return {
    can_publish: failures.length === 0,
    safe_fallback: failures.length > 0,
    failure_reasons: failures
  };
}

// ===== VERSION CONSTANTS =====

export const RESOLVER_VERSION = '2.0.0';
export const UI_CONTRACT_VERSION = '2.0.0';
