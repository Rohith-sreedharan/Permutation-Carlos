import { describe, expect, it } from 'vitest';
import {
  Classification,
  GameEdgeState,
  Grade,
  OfficialAction,
  OfficialMarket,
  ReleaseStatus,
  ValidatorStatus,
} from '../../utils/canonicalEdge';
import { deriveAnalysisGate, getSpreadSummaryContract } from '../../utils/spreadSummaryContract';

function createState(overrides: Partial<GameEdgeState> = {}): GameEdgeState {
  return {
    event_id: 'event-1',
    snapshot_hash: 'hash',
    snapshot_timestamp: new Date().toISOString(),
    resolver_version: 'x',
    ui_contract_version: 'x',
    validator_status: ValidatorStatus.PASS,
    release_status: ReleaseStatus.APPROVED,
    classification: Classification.EDGE,
    official_market: OfficialMarket.SPREAD,
    official_side: 'Home Team',
    official_action: OfficialAction.LAY_POINTS,
    rules_passed: 1,
    rules_total: 1,
    failed_blocking_rules: [],
    failed_scoring_rules: [],
    spread_context: {
      team: 'Home Team',
      team_id: 'home',
      side: 'HOME',
      market_line: -1.5,
      model_line: -2.0,
      edge_gap: 2.0,
      cover_probability_home: 62,
      cover_probability_away: 38,
      grade: Grade.B,
      ev: 2,
      clv: 0,
      volatility_score: 110,
      confidence_score: 60,
      risk_control_log: [],
      blocking_result: { all_passed: true, failed_blocking_rules: [], passed_blocking_rules: [] },
    },
    total_context: {
      side: null,
      market_total: null,
      model_total: null,
      edge_gap: 0,
      over_probability: 50,
      under_probability: 50,
      grade: null,
      ev: 0,
      clv: 0,
      volatility_score: 100,
      confidence_score: 50,
      risk_control_log: [],
      blocking_result: { all_passed: false, failed_blocking_rules: [], passed_blocking_rules: [] },
    },
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
      volatility_score: 100,
      confidence_score: 50,
      risk_control_log: [],
      blocking_result: { all_passed: false, failed_blocking_rules: [], passed_blocking_rules: [] },
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
      parlay_eligible: false,
    },
    assertion_result: {
      all_passed: true,
      assertions: [
        { assertion_id: 'SPREAD_TYPED', passed: true, message: 'Spread properly typed' },
        { assertion_id: 'OFFICIAL_SIDE_PARITY', passed: true, message: 'Official side matches state' },
      ],
    },
    narrative: {
      edge_explanation: '',
      action_summary: '',
      clv_text: '',
      risk_control_summary: '',
    },
    ...overrides,
  };
}

describe('Spread summary contract', () => {
  it('blocks both top summary and detail gate when spread assertions fail', () => {
    const bad = createState({
      spread_context: {
        ...createState().spread_context,
        team: null,
        market_line: null,
      },
      assertion_result: {
        all_passed: false,
        assertions: [
          { assertion_id: 'SPREAD_TYPED', passed: false, message: 'Spread missing team or line' },
          {
            assertion_id: 'OFFICIAL_SIDE_PARITY',
            passed: false,
            message: 'Official side present without EDGE/LEAN classification',
          },
        ],
      },
    });

    const gate = deriveAnalysisGate(bad, false);
    const summary = getSpreadSummaryContract(bad, false);

    expect(gate.blocked).toBe(true);
    expect(summary.blocked).toBe(true);
    expect(summary.marketSpreadLabel).toBeNull();
    expect(summary.modelPreferenceLabel).toBeNull();
  });

  it('derives top summary values from canonical spread context only', () => {
    const good = createState();
    const gate = deriveAnalysisGate(good, true);
    const summary = getSpreadSummaryContract(good, true);

    expect(gate.blocked).toBe(false);
    expect(summary.blocked).toBe(false);
    expect(summary.marketSpreadLabel).toBe('Home Team -1.5');
    expect(summary.fairSpreadLabel).toBe('Home Team -2.0');
    expect(summary.modelPreferenceLabel).toBe('Home Team -1.5');
    expect(summary.edgeConvictionLabel).toBe('Edge Conviction: 62.0%');
  });

  it('does not block total-market decisions on spread-only assertions', () => {
    const totalEdge = createState({
      official_market: OfficialMarket.TOTAL,
      official_action: OfficialAction.OVER,
      official_side: 'OVER',
      spread_context: {
        ...createState().spread_context,
        team: null,
        market_line: null,
      },
      assertion_result: {
        all_passed: true,
        assertions: [
          { assertion_id: 'SPREAD_TYPED', passed: true, message: 'Spread not required for non-spread official market' },
          { assertion_id: 'OFFICIAL_SIDE_PARITY', passed: true, message: 'Official side matches state' },
        ],
      },
    });

    const gate = deriveAnalysisGate(totalEdge, true);
    const summary = getSpreadSummaryContract(totalEdge, true);

    expect(gate.blocked).toBe(false);
    expect(summary.blocked).toBe(false);
    expect(summary.marketSpreadLabel).toBeNull();
    expect(summary.modelPreferenceLabel).toBe('No Detectable Edge');
  });
});
