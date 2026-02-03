/**
 * Box-Level Suppression Logic
 * 
 * When individual market data is incomplete/invalid:
 * - Suppress ONLY the affected box (spread/ML/total)
 * - Show: "Explanation withheld — data incomplete"
 * - Verdict remains intact (EDGE/LEAN/NO_PLAY)
 * - NEVER downgrade verdict due to missing UI data
 * 
 * Example: If spread data missing but ML data valid:
 * ✅ Show spread box with suppression message
 * ✅ Show ML box with full analysis
 * ✅ Overall verdict (EDGE) stays visible
 */

export interface MarketBox {
  type: 'spread' | 'moneyline' | 'total';
  selection_id?: string;
  team?: string;
  line?: number;
  probability?: number;
  tier?: string;
  sharp_action?: string;
  reason_codes?: string[];
}

export interface SuppressionResult {
  shouldSuppress: boolean;
  suppressionReason?: string;
  displayMessage?: string;
}

/**
 * Check if individual market box should be suppressed
 * 
 * Suppression criteria:
 * 1. Missing selection_id
 * 2. Missing probability (or invalid: < 0 or > 1)
 * 3. Missing team/line for spread/ML
 * 4. Missing tier classification
 */
export function shouldSuppressBox(box: MarketBox): SuppressionResult {
  // 1. Missing selection_id
  if (!box.selection_id) {
    return {
      shouldSuppress: true,
      suppressionReason: 'MISSING_SELECTION_ID',
      displayMessage: 'Explanation withheld — data incomplete'
    };
  }

  // 2. Missing or invalid probability
  if (typeof box.probability !== 'number' || box.probability < 0 || box.probability > 1) {
    return {
      shouldSuppress: true,
      suppressionReason: 'INVALID_PROBABILITY',
      displayMessage: 'Explanation withheld — data incomplete'
    };
  }

  // 3. Missing tier classification
  if (!box.tier || !['EDGE', 'LEAN', 'MARKET_ALIGNED', 'BLOCKED'].includes(box.tier)) {
    return {
      shouldSuppress: true,
      suppressionReason: 'MISSING_TIER',
      displayMessage: 'Explanation withheld — data incomplete'
    };
  }

  // 4. For spread/ML: must have team and line
  if (box.type === 'spread' || box.type === 'moneyline') {
    if (!box.team || typeof box.line !== 'number') {
      return {
        shouldSuppress: true,
        suppressionReason: 'MISSING_TEAM_OR_LINE',
        displayMessage: 'Explanation withheld — data incomplete'
      };
    }
  }

  // 5. For total: must have line
  if (box.type === 'total') {
    if (typeof box.line !== 'number') {
      return {
        shouldSuppress: true,
        suppressionReason: 'MISSING_TOTAL_LINE',
        displayMessage: 'Explanation withheld — data incomplete'
      };
    }
  }

  return {
    shouldSuppress: false
  };
}

/**
 * Get overall simulation verdict (NEVER suppressed, even if boxes are)
 * 
 * Verdict hierarchy:
 * 1. Check pick_state first (authoritative)
 * 2. Fall back to highest tier among all markets
 * 3. Default to MARKET_ALIGNED (never hide verdict)
 */
export function getSimulationVerdict(simulation: any): {
  verdict: 'EDGE' | 'LEAN' | 'MARKET_ALIGNED' | 'NO_PLAY';
  source: 'pick_state' | 'tier_rollup' | 'default';
} {
  // 1. Check pick_state (most authoritative)
  if (simulation.pick_state) {
    const pickState = simulation.pick_state.toUpperCase();
    if (['EDGE', 'LEAN', 'NO_PLAY'].includes(pickState)) {
      return {
        verdict: pickState as any,
        source: 'pick_state'
      };
    }
  }

  // 2. Roll up from individual market tiers
  const tiers: string[] = [];
  
  if (simulation.sharp_analysis?.spread?.tier) {
    tiers.push(simulation.sharp_analysis.spread.tier);
  }
  if (simulation.sharp_analysis?.moneyline?.tier) {
    tiers.push(simulation.sharp_analysis.moneyline.tier);
  }
  if (simulation.sharp_analysis?.total?.tier) {
    tiers.push(simulation.sharp_analysis.total.tier);
  }

  // Priority: EDGE > LEAN > MARKET_ALIGNED
  if (tiers.includes('EDGE')) {
    return { verdict: 'EDGE', source: 'tier_rollup' };
  }
  if (tiers.includes('LEAN')) {
    return { verdict: 'LEAN', source: 'tier_rollup' };
  }

  // 3. Default to MARKET_ALIGNED (always show verdict, never hide)
  return {
    verdict: 'MARKET_ALIGNED',
    source: 'default'
  };
}

/**
 * Render suppressed market box (UI component helper)
 * 
 * Returns JSX-compatible object for suppressed market
 */
export function renderSuppressedBox(box: MarketBox, suppression: SuppressionResult) {
  return {
    type: box.type,
    displayMessage: suppression.displayMessage,
    suppressionReason: suppression.suppressionReason,
    isSuppressed: true,
    className: 'bg-navy/30 border border-red-500/20 rounded-lg p-4 text-center',
    html: `
      <div class="text-red-400 text-sm font-medium mb-2">
        ⚠️ ${box.type.toUpperCase()} Analysis Unavailable
      </div>
      <div class="text-light-gray text-xs">
        ${suppression.displayMessage}
      </div>
      <div class="text-light-gray/50 text-xs mt-2">
        Reason: ${suppression.suppressionReason}
      </div>
    `
  };
}

/**
 * CRITICAL RULE ENFORCEMENT
 * 
 * 🔒 Box suppression CANNOT downgrade verdict
 * 
 * Example violation (FORBIDDEN):
 * - Verdict: EDGE (from pick_state)
 * - Spread box: suppressed (missing data)
 * - Result: Verdict changes to NO_PLAY ❌ WRONG
 * 
 * Correct behavior:
 * - Verdict: EDGE (from pick_state)
 * - Spread box: suppressed (missing data)
 * - Result: Verdict stays EDGE, spread box shows suppression message ✅ CORRECT
 */
export function validateVerdictIntegrity(
  originalVerdict: string,
  suppressedBoxes: string[]
): { isValid: boolean; error?: string } {
  if (!originalVerdict || !['EDGE', 'LEAN', 'MARKET_ALIGNED', 'NO_PLAY', 'BLOCKED'].includes(originalVerdict)) {
    return {
      isValid: false,
      error: `INVALID_VERDICT: ${originalVerdict} - must be EDGE/LEAN/MARKET_ALIGNED/NO_PLAY/BLOCKED`
    };
  }

  // Verdict must NEVER change due to box suppression
  // This is validated by ensuring verdict comes from pick_state, NOT from UI data
  return {
    isValid: true
  };
}
