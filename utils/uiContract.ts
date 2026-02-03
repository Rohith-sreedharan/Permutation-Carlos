/**
 * UI CONTRACT ENFORCER - LOCKED
 * ==============================
 * Single source of truth mapping: tier → UI flags → copy
 * 
 * RULE: UI is FORBIDDEN from creating its own tier.
 * Engine outputs tier, UI enforces display rules.
 * 
 * NO CONTRADICTIONS ALLOWED:
 * - If tier=MARKET_ALIGNED → CANNOT show "OFFICIAL EDGE"
 * - If tier=EDGE → CANNOT show "NO EDGE DETECTED"
 * - Model Direction MUST match official selection OR be labeled "informational only"
 */

export type Tier = 'EDGE' | 'LEAN' | 'MARKET_ALIGNED' | 'BLOCKED';

export interface UIFlags {
  // Badges
  showOfficialEdgeBadge: boolean;
  showLeanBadge: boolean;
  showMarketAlignedBanner: boolean;
  showBlockedBanner: boolean;
  
  // Action elements
  showActionSummaryOfficialEdge: boolean;
  showModelPreferenceCard: boolean;
  showTelegramCTA: boolean;
  showPostEligibleIndicator: boolean;
  
  // Informational elements
  showSupportingMetrics: boolean;
  showProbabilities: boolean;
  showFairLineInfo: boolean;
  showGapAsInformational: boolean;
  
  // Negative states
  showNoValidEdgeDetected: boolean;
  showMarketEfficientPricing: boolean;
  
  // Model Direction rules
  modelDirectionMode: 'MIRROR_OFFICIAL' | 'INFORMATIONAL_ONLY' | 'HIDDEN';
  modelDirectionLabel: string | null;
  
  // Execution/sizing
  showWatchLimitSizing: boolean;
  showBlockedReasonCodes: boolean;
}

export interface UICopy {
  headerBadge: string;
  summaryText: string;
  actionText: string | null;
  modelDirectionDisclaimer: string | null;
  forbiddenPhrases: string[];
}

/**
 * Hard-coded UI contract: tier → flags
 * 
 * LOCKED: Do not modify without updating stress tests
 */
export function getTierUIFlags(tier: Tier): UIFlags {
  switch (tier) {
    case 'EDGE':
      return {
        // Badges
        showOfficialEdgeBadge: true,
        showLeanBadge: false,
        showMarketAlignedBanner: false,
        showBlockedBanner: false,
        
        // Action elements
        showActionSummaryOfficialEdge: true,
        showModelPreferenceCard: true,
        showTelegramCTA: true,
        showPostEligibleIndicator: true,
        
        // Informational elements
        showSupportingMetrics: true,
        showProbabilities: true,
        showFairLineInfo: true,
        showGapAsInformational: false, // Not needed for EDGE
        
        // Negative states
        showNoValidEdgeDetected: false,
        showMarketEfficientPricing: false,
        
        // Model Direction rules
        modelDirectionMode: 'MIRROR_OFFICIAL',
        modelDirectionLabel: null, // No disclaimer needed when mirroring
        
        // Execution/sizing
        showWatchLimitSizing: false,
        showBlockedReasonCodes: false,
      };
    
    case 'LEAN':
      return {
        // Badges
        showOfficialEdgeBadge: false,
        showLeanBadge: true,
        showMarketAlignedBanner: false,
        showBlockedBanner: false,
        
        // Action elements
        showActionSummaryOfficialEdge: false, // LEAN is NOT official edge
        showModelPreferenceCard: true,
        showTelegramCTA: false, // LEAN may not be telegram-worthy
        showPostEligibleIndicator: false,
        
        // Informational elements
        showSupportingMetrics: true,
        showProbabilities: true,
        showFairLineInfo: true,
        showGapAsInformational: false,
        
        // Negative states
        showNoValidEdgeDetected: false,
        showMarketEfficientPricing: false,
        
        // Model Direction rules
        modelDirectionMode: 'MIRROR_OFFICIAL',
        modelDirectionLabel: 'Soft edge — proceed with caution',
        
        // Execution/sizing
        showWatchLimitSizing: true,
        showBlockedReasonCodes: false,
      };
    
    case 'MARKET_ALIGNED':
      return {
        // Badges
        showOfficialEdgeBadge: false,
        showLeanBadge: false,
        showMarketAlignedBanner: true,
        showBlockedBanner: false,
        
        // Action elements
        showActionSummaryOfficialEdge: false,
        showModelPreferenceCard: false,
        showTelegramCTA: false,
        showPostEligibleIndicator: false,
        
        // Informational elements
        showSupportingMetrics: true, // Probabilities still informational
        showProbabilities: true,
        showFairLineInfo: true, // Fair line shown as informational
        showGapAsInformational: true, // Gap allowed with disclaimer
        
        // Negative states
        showNoValidEdgeDetected: true,
        showMarketEfficientPricing: true,
        
        // Model Direction rules
        modelDirectionMode: 'INFORMATIONAL_ONLY',
        modelDirectionLabel: 'Informational only — not an official play',
        
        // Execution/sizing
        showWatchLimitSizing: false,
        showBlockedReasonCodes: false,
      };
    
    case 'BLOCKED':
      return {
        // Badges
        showOfficialEdgeBadge: false,
        showLeanBadge: false,
        showMarketAlignedBanner: false,
        showBlockedBanner: true,
        
        // Action elements
        showActionSummaryOfficialEdge: false,
        showModelPreferenceCard: false,
        showTelegramCTA: false,
        showPostEligibleIndicator: false,
        
        // Informational elements
        showSupportingMetrics: false,
        showProbabilities: false,
        showFairLineInfo: false,
        showGapAsInformational: false,
        
        // Negative states
        showNoValidEdgeDetected: false, // BLOCKED is separate from market aligned
        showMarketEfficientPricing: false,
        
        // Model Direction rules
        modelDirectionMode: 'HIDDEN',
        modelDirectionLabel: null,
        
        // Execution/sizing
        showWatchLimitSizing: false,
        showBlockedReasonCodes: true,
      };
  }
}

/**
 * Hard-coded copy templates: tier → copy
 */
export function getTierUICopy(tier: Tier, gapPoints?: number): UICopy {
  switch (tier) {
    case 'EDGE':
      return {
        headerBadge: 'OFFICIAL EDGE',
        summaryText: 'Statistically significant edge detected. All risk controls passed.',
        actionText: 'Official edge validated — execution recommended',
        modelDirectionDisclaimer: null,
        forbiddenPhrases: [
          'MARKET ALIGNED',
          'NO EDGE',
          'No valid edge detected',
          'Market efficiently priced',
        ],
      };
    
    case 'LEAN':
      return {
        headerBadge: 'LEAN',
        summaryText: 'Soft edge detected — proceed with caution. Below institutional threshold.',
        actionText: 'Directional signal only — reduce sizing or monitor',
        modelDirectionDisclaimer: 'Soft edge — not official play',
        forbiddenPhrases: [
          'OFFICIAL EDGE',
          'MARKET ALIGNED',
          'NO EDGE',
          'No valid edge detected',
        ],
      };
    
    case 'MARKET_ALIGNED':
      const gapDisclaimer = gapPoints && gapPoints > 5 
        ? ` Model/market gap detected (${gapPoints.toFixed(1)} pts) — informational only. Monitor live.`
        : '';
      
      return {
        headerBadge: 'MARKET ALIGNED — NO EDGE',
        summaryText: `No valid edge detected. Market appears efficiently priced.${gapDisclaimer}`,
        actionText: null,
        modelDirectionDisclaimer: 'Informational only — not an official play',
        forbiddenPhrases: [
          'OFFICIAL',
          'Official edge',
          'TAKE_POINTS',
          'Action Summary: Official spread edge',
          'Execution recommended',
          'Post eligible',
        ],
      };
    
    case 'BLOCKED':
      return {
        headerBadge: 'BLOCKED',
        summaryText: 'Simulation blocked due to data quality issues. Cannot generate valid analysis.',
        actionText: null,
        modelDirectionDisclaimer: null,
        forbiddenPhrases: [
          'OFFICIAL EDGE',
          'LEAN',
          'MARKET ALIGNED',
          'Official edge',
          'Action Summary',
        ],
      };
  }
}

/**
 * Validate UI state for contradictions
 * 
 * CRITICAL: This MUST pass before rendering
 * Throws error if contradiction detected
 */
export function validateUIContract(tier: Tier, flags: UIFlags): void {
  // Test Group 1: Mutual exclusivity
  if (flags.showOfficialEdgeBadge && flags.showMarketAlignedBanner) {
    throw new Error(
      `UI CONTRACT VIOLATION: Cannot show both Official Edge badge and Market Aligned banner (tier=${tier})`
    );
  }
  
  if (flags.showActionSummaryOfficialEdge && tier !== 'EDGE') {
    throw new Error(
      `UI CONTRACT VIOLATION: Cannot show Action Summary Official Edge when tier=${tier} (only allowed for EDGE)`
    );
  }
  
  if (flags.showNoValidEdgeDetected && (tier === 'EDGE' || tier === 'LEAN')) {
    throw new Error(
      `UI CONTRACT VIOLATION: Cannot show "No valid edge detected" when tier=${tier}`
    );
  }
  
  // Test Group 2: Tier-specific validations
  switch (tier) {
    case 'EDGE':
      if (!flags.showOfficialEdgeBadge) {
        throw new Error('UI CONTRACT VIOLATION: EDGE tier must show Official Edge badge');
      }
      if (flags.showMarketAlignedBanner) {
        throw new Error('UI CONTRACT VIOLATION: EDGE tier cannot show Market Aligned banner');
      }
      if (flags.modelDirectionMode !== 'MIRROR_OFFICIAL') {
        throw new Error('UI CONTRACT VIOLATION: EDGE tier must mirror official selection in Model Direction');
      }
      break;
    
    case 'LEAN':
      if (!flags.showLeanBadge) {
        throw new Error('UI CONTRACT VIOLATION: LEAN tier must show LEAN badge');
      }
      if (flags.showOfficialEdgeBadge) {
        throw new Error('UI CONTRACT VIOLATION: LEAN tier cannot show Official Edge badge');
      }
      if (flags.showMarketAlignedBanner) {
        throw new Error('UI CONTRACT VIOLATION: LEAN tier cannot show Market Aligned banner');
      }
      break;
    
    case 'MARKET_ALIGNED':
      if (!flags.showMarketAlignedBanner) {
        throw new Error('UI CONTRACT VIOLATION: MARKET_ALIGNED tier must show Market Aligned banner');
      }
      if (flags.showOfficialEdgeBadge || flags.showLeanBadge) {
        throw new Error('UI CONTRACT VIOLATION: MARKET_ALIGNED tier cannot show EDGE or LEAN badges');
      }
      if (flags.showActionSummaryOfficialEdge) {
        throw new Error('UI CONTRACT VIOLATION: MARKET_ALIGNED tier cannot show official action summary');
      }
      if (flags.modelDirectionMode !== 'INFORMATIONAL_ONLY') {
        throw new Error('UI CONTRACT VIOLATION: MARKET_ALIGNED tier must label Model Direction as informational only');
      }
      break;
    
    case 'BLOCKED':
      if (!flags.showBlockedBanner) {
        throw new Error('UI CONTRACT VIOLATION: BLOCKED tier must show Blocked banner');
      }
      if (flags.showOfficialEdgeBadge || flags.showLeanBadge || flags.showMarketAlignedBanner) {
        throw new Error('UI CONTRACT VIOLATION: BLOCKED tier cannot show any other tier badges');
      }
      if (flags.modelDirectionMode !== 'HIDDEN') {
        throw new Error('UI CONTRACT VIOLATION: BLOCKED tier must hide Model Direction');
      }
      break;
  }
}

/**
 * Copy linting: Scan rendered text for forbidden phrases
 * 
 * CRITICAL: Prevents regression where tier=MARKET_ALIGNED but shows "OFFICIAL EDGE"
 */
export function lintUICopy(tier: Tier, renderedText: string): string[] {
  const copy = getTierUICopy(tier);
  const violations: string[] = [];
  
  const lowerText = renderedText.toLowerCase();
  
  for (const forbiddenPhrase of copy.forbiddenPhrases) {
    if (lowerText.includes(forbiddenPhrase.toLowerCase())) {
      violations.push(
        `COPY VIOLATION [tier=${tier}]: Forbidden phrase "${forbiddenPhrase}" found in rendered text`
      );
    }
  }
  
  return violations;
}

/**
 * Get complete UI contract for a tier
 * 
 * This is the ONE FUNCTION your components should call
 */
export function getUIContract(tier: Tier, gapPoints?: number): {
  flags: UIFlags;
  copy: UICopy;
  validate: () => void;
  lintText: (text: string) => string[];
} {
  const flags = getTierUIFlags(tier);
  const copy = getTierUICopy(tier, gapPoints);
  
  return {
    flags,
    copy,
    validate: () => validateUIContract(tier, flags),
    lintText: (text: string) => lintUICopy(tier, text),
  };
}

/**
 * Helper: Extract tier from simulation object
 * 
 * Searches in priority order:
 * 1. simulation.tier (if engine sets it)
 * 2. simulation.pick_state → map to tier
 * 3. simulation.classification → map to tier
 * 4. Fallback to MARKET_ALIGNED
 */
export function extractTierFromSimulation(simulation: any): Tier {
  // Direct tier field (preferred)
  if (simulation.tier) {
    const tier = simulation.tier.toUpperCase();
    if (['EDGE', 'LEAN', 'MARKET_ALIGNED', 'BLOCKED'].includes(tier)) {
      return tier as Tier;
    }
  }
  
  // Map from pick_state
  if (simulation.pick_state) {
    const pickState = simulation.pick_state.toUpperCase();
    
    if (pickState === 'PICK' || pickState === 'EDGE') {
      return 'EDGE';
    }
    if (pickState === 'LEAN') {
      return 'LEAN';
    }
    if (pickState === 'NO_PLAY' || pickState === 'NO_ACTION') {
      return 'MARKET_ALIGNED';
    }
    if (pickState === 'BLOCKED' || pickState === 'PENDING_INPUTS') {
      return 'BLOCKED';
    }
  }
  
  // Map from classification
  if (simulation.classification) {
    const classification = simulation.classification.toUpperCase();
    
    if (classification === 'EDGE') {
      return 'EDGE';
    }
    if (classification === 'LEAN') {
      return 'LEAN';
    }
    if (classification === 'NO_ACTION' || classification === 'MARKET_ALIGNED') {
      return 'MARKET_ALIGNED';
    }
    if (classification === 'BLOCKED') {
      return 'BLOCKED';
    }
  }
  
  // Check if suppressed (safety engine blocked)
  if (simulation.safety?.is_suppressed) {
    return 'BLOCKED';
  }
  
  // Fallback: assume market aligned
  console.warn('Could not extract tier from simulation - defaulting to MARKET_ALIGNED');
  return 'MARKET_ALIGNED';
}

/**
 * Helper: Get gap points from simulation
 */
export function extractGapPoints(simulation: any): number | undefined {
  // Try spread analysis
  const spreadAnalysis = simulation.sharp_analysis?.spread;
  if (spreadAnalysis?.edge_points !== undefined) {
    return Math.abs(spreadAnalysis.edge_points);
  }
  
  // Try total analysis
  const totalAnalysis = simulation.sharp_analysis?.total;
  if (totalAnalysis?.edge_points !== undefined) {
    return Math.abs(totalAnalysis.edge_points);
  }
  
  // Try direct delta
  if (simulation.divergence_score !== undefined) {
    return Math.abs(simulation.divergence_score);
  }
  
  return undefined;
}
