import { Classification, GameEdgeState, OfficialMarket } from './canonicalEdge';

export interface AnalysisGateResult {
  blocked: boolean;
  reason: string;
}

export interface SpreadSummaryContract {
  blocked: boolean;
  reason: string;
  marketSpreadLabel: string | null;
  fairSpreadLabel: string | null;
  modelPreferenceLabel: string | null;
  edgeConvictionLabel: string | null;
}

function formatSigned(line: number): string {
  return line >= 0 ? `+${line.toFixed(1)}` : line.toFixed(1);
}

function assertionPassed(state: GameEdgeState, assertionId: string): boolean {
  const match = state.assertion_result.assertions.find((a) => a.assertion_id === assertionId);
  return !!match?.passed;
}

/**
 * Shared fail-closed gate used by both top summary and detail rendering.
 */
export function deriveAnalysisGate(
  state: GameEdgeState | null,
  canRender: boolean
): AnalysisGateResult {
  if (!state) {
    return { blocked: true, reason: 'No canonical edge state available' };
  }

  if (!canRender || !state.assertion_result.all_passed) {
    return { blocked: true, reason: 'Pre-render assertions failed' };
  }

  if (state.classification === Classification.BLOCKED) {
    return { blocked: true, reason: 'Classification is BLOCKED' };
  }

  return { blocked: false, reason: '' };
}

/**
 * Derive spread summary labels from the same canonical state/gate as detail UI.
 * This prevents independent top-card derivations from diverging.
 */
export function getSpreadSummaryContract(
  state: GameEdgeState | null,
  canRender: boolean
): SpreadSummaryContract {
  const gate = deriveAnalysisGate(state, canRender);
  if (gate.blocked || !state) {
    return {
      blocked: true,
      reason: gate.reason,
      marketSpreadLabel: null,
      fairSpreadLabel: null,
      modelPreferenceLabel: null,
      edgeConvictionLabel: null,
    };
  }

  const spreadTyped = assertionPassed(state, 'SPREAD_TYPED');
  const sideParity = assertionPassed(state, 'OFFICIAL_SIDE_PARITY');

  // Spread summary is informational when the official market is not spread.
  // Do not fail-close the entire detail page for non-spread decisions.
  if (state.official_market !== OfficialMarket.SPREAD) {
    return {
      blocked: false,
      reason: '',
      marketSpreadLabel: null,
      fairSpreadLabel: null,
      modelPreferenceLabel: 'No Detectable Edge',
      edgeConvictionLabel: 'No Detectable Edge',
    };
  }

  if (!spreadTyped || !sideParity) {
    return {
      blocked: true,
      reason: 'Spread assertions failed',
      marketSpreadLabel: null,
      fairSpreadLabel: null,
      modelPreferenceLabel: null,
      edgeConvictionLabel: null,
    };
  }

  const spread = state.spread_context;
  if (!spread.team || spread.market_line === null) {
    return {
      blocked: true,
      reason: 'Spread missing team or line',
      marketSpreadLabel: null,
      fairSpreadLabel: null,
      modelPreferenceLabel: null,
      edgeConvictionLabel: null,
    };
  }

  const marketSpreadLabel = `${spread.team} ${formatSigned(spread.market_line)}`;
  const fairSpreadLabel =
    spread.model_line === null ? null : `${spread.team} ${formatSigned(spread.model_line)}`;

  let modelPreferenceLabel: string | null = null;
  let edgeConvictionLabel: string | null = null;

  if (
    (state.classification === Classification.EDGE || state.classification === Classification.LEAN) &&
    state.official_market === 'SPREAD' &&
    spread.side
  ) {
    modelPreferenceLabel = marketSpreadLabel;
    const prob =
      spread.side === 'HOME'
        ? spread.cover_probability_home
        : spread.cover_probability_away;
    edgeConvictionLabel = `Edge Conviction: ${prob.toFixed(1)}%`;
  } else {
    modelPreferenceLabel = 'No Detectable Edge';
    edgeConvictionLabel = 'No Detectable Edge';
  }

  return {
    blocked: false,
    reason: '',
    marketSpreadLabel,
    fairSpreadLabel,
    modelPreferenceLabel,
    edgeConvictionLabel,
  };
}
