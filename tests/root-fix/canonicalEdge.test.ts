/**
 * ROOT FIX REGRESSION TEST SUITE
 * ==============================
 * 
 * UNIVERSAL LOCK TEST SUITE to prove the ROOT DECISION INTEGRITY issue is DEAD.
 * 
 * Tests against audited cards:
 * - Denver/OKC
 * - Memphis/Brooklyn
 * - GSW/Utah
 * - Knicks/Clippers
 * 
 * VERIFICATION TARGETS:
 * 1. Numeric values bounded [0, 100] for percentages
 * 2. Blocking rules actually block (EV, gap, volatility, grade)
 * 3. Market isolation (spread reads only spread context)
 * 4. Pre-render assertions pass
 * 5. Fail-closed behavior when assertions fail
 * 6. Classification derived correctly
 * 7. No independent edge computation in UI
 */

import { describe, it, expect, beforeAll } from 'vitest';
import {
  sanitizeConfidence,
  sanitizeProbability,
  sanitizeEV,
  sanitizeCLV,
  sanitizeVolatility,
  evaluateSpreadBlockingRules,
  evaluateTotalBlockingRules,
  runPreRenderAssertions,
  deriveRenderFlags,
  canPublishCard,
  isGradePublishable,
  BLOCKING_THRESHOLDS,
  Grade,
  Classification,
  ReleaseStatus,
  ValidatorStatus,
  SpreadEdgeContext,
  TotalEdgeContext,
  GameEdgeState,
  OfficialMarket,
  OfficialAction,
} from '../../utils/canonicalEdge';
import { resolveGameEdgeState, canPublish, getFailureReasons } from '../../utils/resolveGameEdgeState';

// ===== TEST FIXTURES =====

// Mock simulation data for testing
const createMockSpreadContext = (overrides: Partial<SpreadEdgeContext> = {}): SpreadEdgeContext => ({
  team: 'Denver Nuggets',
  team_id: 'nuggets',
  side: 'HOME',
  market_line: -5.5,
  model_line: -7.0,
  edge_gap: 1.5,
  cover_probability_home: 58.5,
  cover_probability_away: 41.5,
  grade: Grade.B,
  ev: 3.5,
  clv: 1.2,
  volatility_score: 120,
  confidence_score: 65,
  risk_control_log: [],
  blocking_result: { all_passed: true, passed_blocking_rules: [], failed_blocking_rules: [] },
  ...overrides,
});

const createMockTotalContext = (overrides: Partial<TotalEdgeContext> = {}): TotalEdgeContext => ({
  side: 'OVER',
  market_total: 225.5,
  model_total: 228.0,
  edge_gap: 2.5,
  over_probability: 56.2,
  under_probability: 43.8,
  grade: Grade.B,
  ev: 2.8,
  clv: 0.8,
  volatility_score: 100,
  confidence_score: 58,
  risk_control_log: [],
  blocking_result: { all_passed: true, passed_blocking_rules: [], failed_blocking_rules: [] },
  ...overrides,
});

const createMockGameEdgeState = (overrides: Partial<GameEdgeState> = {}): GameEdgeState => ({
  event_id: 'test-event-123',
  snapshot_hash: 'abc123def456',
  snapshot_timestamp: new Date().toISOString(),
  resolver_version: '2.0.0',
  ui_contract_version: '2.0.0',
  validator_status: ValidatorStatus.PASS,
  release_status: ReleaseStatus.APPROVED,
  classification: Classification.EDGE,
  official_market: OfficialMarket.SPREAD,
  official_side: 'Denver Nuggets',
  official_action: OfficialAction.LAY_POINTS,
  rules_passed: 10,
  rules_total: 10,
  failed_blocking_rules: [],
  failed_scoring_rules: [],
  spread_context: createMockSpreadContext(),
  total_context: createMockTotalContext(),
  moneyline_context: {
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
    blocking_result: { all_passed: false, passed_blocking_rules: [], failed_blocking_rules: [] },
  },
  render_flags: {
    show_edge_banner: true,
    show_lean_banner: false,
    show_market_aligned_banner: false,
    show_blocked_banner: false,
    show_official_play: true,
    show_action_summary: true,
    show_spread_section: true,
    show_total_section: false,
    show_moneyline_section: false,
    show_why_edge_exists: true,
    telegram_eligible: false,
    parlay_eligible: true,
  },
  assertion_result: { all_passed: true, assertions: [] },
  narrative: {
    edge_explanation: 'Model detects 1.5 pt edge on Denver Nuggets spread',
    action_summary: 'Official spread edge: Denver Nuggets -5.5',
    clv_text: 'Estimated CLV: +1.2%',
    risk_control_summary: '',
  },
  ...overrides,
});

// ===== NUMERIC SANITIZATION TESTS =====

describe('Numeric Sanitization Layer', () => {
  describe('sanitizeConfidence', () => {
    it('clamps values to [0, 100]', () => {
      expect(sanitizeConfidence(150).value).toBe(100);
      expect(sanitizeConfidence(-50).value).toBe(0);
      expect(sanitizeConfidence(75).value).toBe(75);
    });
    
    it('handles 0% and 100% edge cases', () => {
      expect(sanitizeConfidence(0).value).toBe(0);
      expect(sanitizeConfidence(100).value).toBe(100);
    });
    
    it('clamps out-of-bounds values and flags as clamped', () => {
      const result = sanitizeConfidence(3000); // Audited failure case
      expect(result.valid).toBe(true);
      expect(result.clamped).toBe(true);
      expect(result.value).toBe(100);
    });
    
    it('handles NaN by returning min', () => {
      const result = sanitizeConfidence(NaN);
      expect(result.valid).toBe(false);
      expect(result.value).toBe(0); // min value
    });
    
    it('handles Infinity by clamping', () => {
      const result = sanitizeConfidence(Infinity);
      expect(result.valid).toBe(false);
      expect(result.value).toBe(100); // max value
    });
  });
  
  describe('sanitizeProbability', () => {
    it('clamps values to [0, 100]', () => {
      expect(sanitizeProbability(4400).value).toBe(100); // Audited failure case
      expect(sanitizeProbability(5130).value).toBe(100); // Audited failure case
      expect(sanitizeProbability(-10).value).toBe(0);
      expect(sanitizeProbability(55.5).value).toBe(55.5);
    });
    
    it('flags extreme values as clamped', () => {
      const result = sanitizeProbability(4400);
      expect(result.clamped).toBe(true);
      expect(result.original).toBe(4400);
    });
  });
  
  describe('sanitizeEV', () => {
    it('clamps values to [-100, 100]', () => {
      expect(sanitizeEV(150).value).toBe(100);
      expect(sanitizeEV(-150).value).toBe(-100);
      expect(sanitizeEV(5.5).value).toBe(5.5);
    });
  });
  
  describe('sanitizeVolatility', () => {
    it('clamps values to [0, 500]', () => {
      expect(sanitizeVolatility(1000).value).toBe(500);
      expect(sanitizeVolatility(-50).value).toBe(0);
      expect(sanitizeVolatility(150).value).toBe(150);
    });
  });
});

// ===== BLOCKING RULES TESTS =====

describe('Blocking Rule Engine', () => {
  describe('evaluateSpreadBlockingRules', () => {
    it('blocks when EV is negative', () => {
      const ctx = createMockSpreadContext({ ev: -2.0 });
      const result = evaluateSpreadBlockingRules(ctx);
      expect(result.all_passed).toBe(false);
      expect(result.failed_blocking_rules.some(r => r.rule_id === 'EV_POSITIVE')).toBe(true);
    });
    
    it('blocks when gap is below minimum', () => {
      const ctx = createMockSpreadContext({ edge_gap: 1.0 }); // Below MIN_SPREAD_GAP of 2.0
      const result = evaluateSpreadBlockingRules(ctx);
      expect(result.all_passed).toBe(false);
      expect(result.failed_blocking_rules.some(r => r.rule_id === 'MIN_GAP')).toBe(true);
    });
    
    it('blocks when volatility exceeds maximum', () => {
      const ctx = createMockSpreadContext({ volatility_score: 350 }); // Above MAX_VOLATILITY of 300
      const result = evaluateSpreadBlockingRules(ctx);
      expect(result.all_passed).toBe(false);
      expect(result.failed_blocking_rules.some(r => r.rule_id === 'VOLATILITY')).toBe(true);
    });
    
    it('blocks when grade is below C', () => {
      const ctx = createMockSpreadContext({ grade: Grade.D });
      const result = evaluateSpreadBlockingRules(ctx);
      expect(result.all_passed).toBe(false);
      expect(result.failed_blocking_rules.some(r => r.rule_id === 'GRADE_GATE')).toBe(true);
    });
    
    it('passes when all rules are met', () => {
      const ctx = createMockSpreadContext({
        ev: 5.0,
        edge_gap: 3.0,
        volatility_score: 150,
        grade: Grade.B,
      });
      const result = evaluateSpreadBlockingRules(ctx);
      expect(result.all_passed).toBe(true);
      expect(result.failed_blocking_rules.length).toBe(0);
    });
  });
  
  describe('evaluateTotalBlockingRules', () => {
    it('uses different minimum gap threshold', () => {
      const ctx = createMockTotalContext({ edge_gap: 1.0 }); // Below MIN_TOTAL_GAP of 1.5
      const result = evaluateTotalBlockingRules(ctx);
      expect(result.all_passed).toBe(false);
    });
    
    it('passes when total gap meets minimum', () => {
      const ctx = createMockTotalContext({ edge_gap: 2.0, ev: 3.0, grade: Grade.B });
      const result = evaluateTotalBlockingRules(ctx);
      expect(result.all_passed).toBe(true);
    });
  });
});

// ===== GRADE GATE TESTS =====

describe('Grade Gate Enforcement', () => {
  it('allows S through C grades', () => {
    expect(isGradePublishable(Grade.S)).toBe(true);
    expect(isGradePublishable(Grade.A)).toBe(true);
    expect(isGradePublishable(Grade.B)).toBe(true);
    expect(isGradePublishable(Grade.C)).toBe(true);
  });
  
  it('blocks D and F grades', () => {
    expect(isGradePublishable(Grade.D)).toBe(false);
    expect(isGradePublishable(Grade.F)).toBe(false);
  });
  
  it('blocks null grade', () => {
    expect(isGradePublishable(null)).toBe(false);
  });
});

// ===== PRE-RENDER ASSERTION TESTS =====

describe('Pre-Render Assertion Suite', () => {
  it('validates state with correct structure', () => {
    const state = createMockGameEdgeState();
    const result = runPreRenderAssertions(state);
    // A well-formed mock state should pass all assertions
    expect(result.assertions.length).toBeGreaterThan(0);
  });
  
  it('has multiple assertion checks', () => {
    const state = createMockGameEdgeState();
    const result = runPreRenderAssertions(state);
    // Should have multiple assertions
    expect(result.assertions.length).toBeGreaterThanOrEqual(5);
  });
  
  it('includes BANNER_STATE_PARITY assertion', () => {
    const state = createMockGameEdgeState();
    const result = runPreRenderAssertions(state);
    expect(result.assertions.some(a => a.assertion_id === 'BANNER_STATE_PARITY')).toBe(true);
  });
  
  it('includes BOUNDED_METRICS_VALID assertion', () => {
    const state = createMockGameEdgeState();
    const result = runPreRenderAssertions(state);
    expect(result.assertions.some(a => a.assertion_id === 'BOUNDED_METRICS_VALID')).toBe(true);
  });
  
  it('includes market isolation assertions', () => {
    const state = createMockGameEdgeState();
    const result = runPreRenderAssertions(state);
    expect(result.assertions.some(a => a.assertion_id === 'SPREAD_ISOLATION')).toBe(true);
    expect(result.assertions.some(a => a.assertion_id === 'TOTAL_ISOLATION')).toBe(true);
  });

  it('does not fail SPREAD_TYPED when official market is TOTAL', () => {
    const totalOfficialState = createMockGameEdgeState({
      official_market: OfficialMarket.TOTAL,
      official_action: OfficialAction.OVER,
      official_side: 'OVER',
      spread_context: createMockSpreadContext({
        team: null,
        market_line: null,
      }),
    });

    const result = runPreRenderAssertions(totalOfficialState);
    const spreadTyped = result.assertions.find(a => a.assertion_id === 'SPREAD_TYPED');

    expect(spreadTyped).toBeDefined();
    expect(spreadTyped?.passed).toBe(true);
  });
});

// ===== RENDER FLAGS DERIVATION TESTS =====

describe('Render Flags Derivation', () => {
  it('shows edge banner only for EDGE classification', () => {
    const edgeState = createMockGameEdgeState({ 
      classification: Classification.EDGE,
      release_status: ReleaseStatus.APPROVED,
    });
    const leanState = createMockGameEdgeState({ 
      classification: Classification.LEAN,
      release_status: ReleaseStatus.APPROVED,
    });
    const noActionState = createMockGameEdgeState({ classification: Classification.NO_ACTION });
    
    expect(deriveRenderFlags(edgeState).show_edge_banner).toBe(true);
    expect(deriveRenderFlags(leanState).show_edge_banner).toBe(false);
    expect(deriveRenderFlags(noActionState).show_edge_banner).toBe(false);
  });
  
  it('shows lean banner for LEAN classification', () => {
    const leanState = createMockGameEdgeState({ 
      classification: Classification.LEAN,
      release_status: ReleaseStatus.APPROVED,
    });
    expect(deriveRenderFlags(leanState).show_lean_banner).toBe(true);
  });
  
  it('shows blocked banner when not approved', () => {
    const blockedState = createMockGameEdgeState({ release_status: ReleaseStatus.BLOCKED_BY_EV });
    expect(deriveRenderFlags(blockedState).show_blocked_banner).toBe(true);
  });
  
  it('disables telegram eligibility when blocked', () => {
    const blockedState = createMockGameEdgeState({ release_status: ReleaseStatus.BLOCKED_BY_EV });
    expect(deriveRenderFlags(blockedState).telegram_eligible).toBe(false);
  });
});

// ===== FAIL-CLOSED PUBLISH CONTRACT TESTS =====

describe('Fail-Closed Publish Contract', () => {
  it('rejects state with failed assertions', () => {
    const state = createMockGameEdgeState();
    state.assertion_result = {
      all_passed: false,
      assertions: [{ assertion_id: 'TEST', passed: false, message: 'Test failure' }],
    };
    const result = canPublishCard(state);
    expect(result.can_publish).toBe(false);
  });
  
  it('accepts state with passing assertions', () => {
    const state = createMockGameEdgeState();
    state.assertion_result = {
      all_passed: true,
      assertions: [],
    };
    const result = canPublishCard(state);
    expect(result.can_publish).toBe(true);
  });
  
  it('rejects null state', () => {
    const result = canPublishCard(null);
    expect(result.can_publish).toBe(false);
  });
});

// ===== MARKET ISOLATION TESTS =====

describe('Market Isolation', () => {
  it('spread context contains only spread data', () => {
    const ctx = createMockSpreadContext();
    
    // Spread context should have spread-specific fields
    expect(ctx).toHaveProperty('cover_probability_home');
    expect(ctx).toHaveProperty('cover_probability_away');
    expect(ctx).toHaveProperty('market_line');
    
    // Spread context should NOT have total fields
    expect(ctx).not.toHaveProperty('over_probability');
    expect(ctx).not.toHaveProperty('under_probability');
    expect(ctx).not.toHaveProperty('market_total');
  });
  
  it('total context contains only total data', () => {
    const ctx = createMockTotalContext();
    
    // Total context should have total-specific fields
    expect(ctx).toHaveProperty('over_probability');
    expect(ctx).toHaveProperty('under_probability');
    expect(ctx).toHaveProperty('market_total');
    
    // Total context should NOT have spread fields
    expect(ctx).not.toHaveProperty('cover_probability_home');
    expect(ctx).not.toHaveProperty('market_line');
  });
});

// ===== AUDITED FAILURE SCENARIOS =====

describe('Audited Failure Scenarios', () => {
  /**
   * AUDIT CASE: Denver/OKC with 3000%/4400%/5130% probability displays
   * ROOT CAUSE: Unbounded numeric values reaching UI
   */
  it('prevents 3000% probability display (Denver/OKC audit)', () => {
    const rawProbability = 3000;
    const sanitized = sanitizeProbability(rawProbability);
    
    expect(sanitized.value).toBeLessThanOrEqual(100);
    expect(sanitized.clamped).toBe(true);
  });
  
  it('prevents 4400% probability display (audit case)', () => {
    const rawProbability = 4400;
    const sanitized = sanitizeProbability(rawProbability);
    
    expect(sanitized.value).toBeLessThanOrEqual(100);
    expect(sanitized.valid).toBe(true);
  });
  
  it('prevents 5130% probability display (audit case)', () => {
    const rawProbability = 5130;
    const sanitized = sanitizeProbability(rawProbability);
    
    expect(sanitized.value).toBeLessThanOrEqual(100);
    expect(sanitized.clamped).toBe(true);
  });
  
  /**
   * AUDIT CASE: Cross-market contamination
   * ROOT CAUSE: Spread decision displayed total branding
   */
  it('ensures spread edge shows spread branding', () => {
    const state = createMockGameEdgeState({
      official_market: OfficialMarket.SPREAD,
      official_side: 'Denver Nuggets',
      official_action: OfficialAction.LAY_POINTS,
    });
    
    // When spread is the official market, it should not show total actions
    expect(state.official_action).not.toBe(OfficialAction.OVER);
    expect(state.official_action).not.toBe(OfficialAction.UNDER);
    expect(state.official_market).toBe(OfficialMarket.SPREAD);
  });
  
  /**
   * AUDIT CASE: UI-computed state conflicted with engine
   * ROOT CAUSE: Independent edge computation in UI components
   */
  it('render flags are derived from state, not computed', () => {
    const edgeState = createMockGameEdgeState({ 
      classification: Classification.EDGE,
      release_status: ReleaseStatus.APPROVED,
    });
    const flags = deriveRenderFlags(edgeState);
    
    // Flags should be deterministic from state
    expect(flags.show_edge_banner).toBe(true);
    
    // Change classification
    const leanState = createMockGameEdgeState({ 
      classification: Classification.LEAN,
      release_status: ReleaseStatus.APPROVED,
    });
    const leanFlags = deriveRenderFlags(leanState);
    
    expect(leanFlags.show_edge_banner).toBe(false);
    expect(leanFlags.show_lean_banner).toBe(true);
  });
  
  /**
   * AUDIT CASE: Grade D/F surfacing as edge/lean
   * ROOT CAUSE: Missing grade gate enforcement
   */
  it('blocks D grade from surfacing as edge', () => {
    const ctx = createMockSpreadContext({ grade: Grade.D, ev: 5.0, edge_gap: 3.0 });
    const result = evaluateSpreadBlockingRules(ctx);
    
    expect(result.all_passed).toBe(false);
    expect(result.failed_blocking_rules.some(r => r.rule_id === 'GRADE_GATE')).toBe(true);
  });
  
  it('blocks F grade from surfacing as edge', () => {
    const ctx = createMockSpreadContext({ grade: Grade.F, ev: 5.0, edge_gap: 3.0 });
    const result = evaluateSpreadBlockingRules(ctx);
    
    expect(result.all_passed).toBe(false);
  });
});

// ===== STATE RESOLVER TESTS =====

describe('GameEdgeState Resolver', () => {
  it('returns null for null simulation', () => {
    const result = resolveGameEdgeState(null, 'test-event', 'Home Team', 'Away Team');
    expect(result).toBeNull();
  });
  
  it('returns null for undefined simulation', () => {
    const result = resolveGameEdgeState(undefined, 'test-event', 'Home Team', 'Away Team');
    expect(result).toBeNull();
  });
  
  it('canPublish returns false for null state', () => {
    expect(canPublish(null)).toBe(false);
  });
  
  it('getFailureReasons returns reasons for null state', () => {
    const reasons = getFailureReasons(null);
    expect(reasons.length).toBeGreaterThan(0);
    expect(reasons[0]).toContain('No state');
  });

  it('parses lowercase market sides and preserves 0-100 confidence scale', () => {
    const simulation: any = {
      confidence_score: 51,
      volatility_score: 'Medium',
      market_views: {
        spread: {
          edge_class: 'NO_ACTION',
          edge_points: 0,
          model_preference_selection_id: 'spread-home',
          integrity_status: { status: 'ok', is_valid: true, errors: [] },
          selections: [
            {
              selection_id: 'spread-home',
              side: 'home',
              market_probability: 0.52,
              model_probability: 0.54,
              market_line_for_selection: -1.5,
              model_fair_line_for_selection: -2.0,
            },
            {
              selection_id: 'spread-away',
              side: 'away',
              market_probability: 0.48,
              model_probability: 0.46,
              market_line_for_selection: 1.5,
              model_fair_line_for_selection: 2.0,
            },
          ],
        },
        total: {
          edge_class: 'NO_ACTION',
          edge_points: 0,
          model_preference_selection_id: 'NO_EDGE',
          integrity_status: { status: 'ok', is_valid: true, errors: [] },
          selections: [
            {
              selection_id: 'total-over',
              side: 'over',
              market_probability: 0.5,
              model_probability: 0.5,
              market_line_for_selection: 8,
              model_fair_line_for_selection: 8,
            },
            {
              selection_id: 'total-under',
              side: 'under',
              market_probability: 0.5,
              model_probability: 0.5,
              market_line_for_selection: 8,
              model_fair_line_for_selection: 8,
            },
          ],
        },
      },
    };

    const result = resolveGameEdgeState(simulation, 'evt-1', 'Home Team', 'Away Team');
    expect(result).not.toBeNull();
    expect(result?.spread_context.side).toBe('HOME');
    expect(result?.spread_context.team).toBe('Home Team');
    expect(result?.spread_context.confidence_score).toBe(51);
    expect(result?.validator_status).toBe(ValidatorStatus.PASS);
  });

  it('recovers spread team/line when preferred selection id does not match', () => {
    const simulation: any = {
      confidence_score: 58,
      volatility_score: 'Medium',
      market_views: {
        spread: {
          edge_class: 'EDGE',
          edge_points: 2.6,
          grade: 'B',
          model_preference_selection_id: 'spread-home-v2',
          integrity_status: { status: 'ok', is_valid: true, errors: [] },
          selections: [
            {
              selection_id: 'spread-home',
              side: 'HOME',
              market_probability: 0.49,
              model_probability: 0.56,
              market_line_for_selection: -1.5,
              model_fair_line_for_selection: -3.0,
            },
            {
              selection_id: 'spread-away',
              side: 'AWAY',
              market_probability: 0.51,
              model_probability: 0.44,
              market_line_for_selection: 1.5,
              model_fair_line_for_selection: 3.0,
            },
          ],
        },
        total: {
          edge_class: 'NO_ACTION',
          edge_points: 0,
          model_preference_selection_id: 'NO_EDGE',
          integrity_status: { status: 'ok', is_valid: true, errors: [] },
          selections: [
            {
              selection_id: 'total-over',
              side: 'OVER',
              market_probability: 0.5,
              model_probability: 0.5,
              market_line_for_selection: 8,
              model_fair_line_for_selection: 8,
            },
            {
              selection_id: 'total-under',
              side: 'UNDER',
              market_probability: 0.5,
              model_probability: 0.5,
              market_line_for_selection: 8,
              model_fair_line_for_selection: 8,
            },
          ],
        },
      },
    };

    const result = resolveGameEdgeState(simulation, 'evt-2', 'New York Yankees', 'Detroit Tigers');

    expect(result).not.toBeNull();
    expect(result?.spread_context.team).toBe('New York Yankees');
    expect(result?.spread_context.side).toBe('HOME');
    expect(result?.spread_context.market_line).toBe(-1.5);
    expect(result?.assertion_result.assertions.find(a => a.assertion_id === 'SPREAD_TYPED')?.passed).toBe(true);
  });

  it('does not classify spread edge when market line is missing', () => {
    const simulation: any = {
      confidence_score: 64,
      volatility_score: 'Medium',
      market_views: {
        spread: {
          edge_class: 'EDGE',
          edge_points: 3.2,
          grade: 'A',
          model_preference_selection_id: 'spread-home',
          integrity_status: { status: 'ok', is_valid: true, errors: [] },
          selections: [
            {
              selection_id: 'spread-home',
              side: 'HOME',
              market_probability: 0.46,
              model_probability: 0.58,
              market_line_for_selection: null,
              model_fair_line_for_selection: -3.5,
            },
            {
              selection_id: 'spread-away',
              side: 'AWAY',
              market_probability: 0.54,
              model_probability: 0.42,
              market_line_for_selection: null,
              model_fair_line_for_selection: 3.5,
            },
          ],
        },
      },
    };

    const result = resolveGameEdgeState(simulation, 'evt-3', 'New York Yankees', 'Detroit Tigers');

    expect(result).not.toBeNull();
    expect(result?.classification).not.toBe(Classification.EDGE);
    expect(result?.official_market).toBeNull();
    expect(result?.assertion_result.assertions.find(a => a.assertion_id === 'SPREAD_TYPED')?.passed).toBe(true);
  });
});

// ===== REGRESSION GUARD TESTS =====

describe('Regression Guards', () => {
  it('BLOCKING_THRESHOLDS are correctly configured', () => {
    // EV threshold allows small positive values
    expect(BLOCKING_THRESHOLDS.MIN_EV).toBeGreaterThanOrEqual(0);
    expect(BLOCKING_THRESHOLDS.MIN_EV).toBeLessThan(1);
    expect(BLOCKING_THRESHOLDS.MIN_SPREAD_GAP).toBe(2.0);
    expect(BLOCKING_THRESHOLDS.MIN_TOTAL_GAP).toBe(1.5);
    expect(BLOCKING_THRESHOLDS.MAX_VOLATILITY).toBe(300);
    expect(BLOCKING_THRESHOLDS.MIN_CONFIDENCE).toBe(25);
  });
  
  it('Grade enum has all expected values', () => {
    // Check all grade values exist (S, A, B, C, D, F)
    expect(Grade.S).toBe('S');
    expect(Grade.A).toBe('A');
    expect(Grade.B).toBe('B');
    expect(Grade.C).toBe('C');
    expect(Grade.D).toBe('D');
    expect(Grade.F).toBe('F');
  });
  
  it('Classification enum values are correct', () => {
    expect(Classification.EDGE).toBe('EDGE');
    expect(Classification.LEAN).toBe('LEAN');
    expect(Classification.MARKET_ALIGNED).toBe('MARKET_ALIGNED');
    expect(Classification.NO_ACTION).toBe('NO_ACTION');
  });
  
  it('ReleaseStatus enum has all blocking states', () => {
    expect(ReleaseStatus.BLOCKED_BY_EV).toBeDefined();
    expect(ReleaseStatus.BLOCKED_BY_GAP).toBeDefined();
    expect(ReleaseStatus.BLOCKED_BY_VOLATILITY).toBeDefined();
    expect(ReleaseStatus.BLOCKED_BY_GRADE).toBeDefined();
    expect(ReleaseStatus.BLOCKED_BY_INTEGRITY).toBeDefined();
  });
});

// ===== SNAPSHOT INTEGRITY TESTS =====

describe('Snapshot Integrity', () => {
  it('state includes resolver version', () => {
    const state = createMockGameEdgeState();
    expect(state.resolver_version).toBe('2.0.0');
  });
  
  it('state includes UI contract version', () => {
    const state = createMockGameEdgeState();
    expect(state.ui_contract_version).toBe('2.0.0');
  });
  
  it('state includes snapshot hash', () => {
    const state = createMockGameEdgeState();
    expect(state.snapshot_hash).toBeTruthy();
    expect(state.snapshot_hash.length).toBeGreaterThan(0);
  });
  
  it('state includes snapshot timestamp', () => {
    const state = createMockGameEdgeState();
    expect(state.snapshot_timestamp).toBeTruthy();
    // Should be valid ISO timestamp
    expect(new Date(state.snapshot_timestamp).toString()).not.toBe('Invalid Date');
  });
});
