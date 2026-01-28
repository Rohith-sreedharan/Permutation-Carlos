/**
 * MODEL SPREAD & SHARP SIDE LOGIC — LOCKED DEFINITION
 * ====================================================
 * This module is the SINGLE SOURCE OF TRUTH for model spread interpretation.
 * 
 * 🚨 LOCKED: Do NOT modify this logic without explicit approval.
 * 
 * CANONICAL RULE:
 * --------------
 * Model Spread is a SIGNED value relative to TEAM DIRECTION:
 * • Positive (+) Model Spread → Underdog spread
 * • Negative (−) Model Spread → Favorite spread
 * 
 * SHARP SIDE SELECTION (CORRECTED LOGIC):
 * --------------------------------------
 * • If model_spread > market_spread → Sharp side = UNDERDOG (dog getting too few points = undervalued)
 * • If model_spread < market_spread → Sharp side = FAVORITE (dog getting too many points = fav undervalued)
 * 
 * EXAMPLES:
 * ---------
 * Example 1 — Underdog Undervalued
 *   Market: Hawks +5.5, Knicks -5.5
 *   Model Spread: +12.3
 *   
 *   model_spread (+12.3) > market_spread (+5.5) → Sharp side = UNDERDOG (Hawks +5.5)
 *   Reason: Model says Hawks should get +12.3, but only getting +5.5 → Hawks undervalued
 * 
 * Example 2 — Favorite Undervalued
 *   Market: Hawks +5.5, Knicks -5.5
 *   Model Spread: +3.2
 *   
 *   model_spread (+3.2) < market_spread (+5.5) → Sharp side = FAVORITE (Knicks -5.5)
 *   Reason: Model says Hawks should only get +3.2, but getting +5.5 → Knicks undervalued
 */

export type SharpSideCode = 'FAV' | 'DOG';

export interface SpreadContext {
  // Team info
  homeTeam: string;
  awayTeam: string;
  
  // Market spreads
  marketSpreadHome: number;  // e.g., -5.5 (home is favorite)
  marketSpreadAway: number;  // e.g., +5.5 (away is underdog)
  
  // Model spread (signed, from underdog perspective)
  modelSpread: number;  // Positive = underdog, Negative = favorite
  
  // Derived: Which team is favored
  marketFavorite: string;
  marketUnderdog: string;
  
  // Derived: Sharp side
  sharpSide: SharpSideCode;
  sharpSideTeam: string;
  sharpSideLine: number;
  
  // Display strings (MANDATORY for UI)
  marketSpreadDisplay: string;    // "Hawks +5.5"
  modelSpreadDisplay: string;     // "Hawks +12.3" (with team!)
  sharpSideDisplay: string;       // "Knicks -5.5" (explicit!)
  
  // Edge metrics
  edgePoints: number;
  edgeDirection: SharpSideCode;
}

/**
 * UNIVERSAL SHARP SIDE SELECTION RULE (CORRECTED)
 * 
 * @param modelSpread - Signed model output (+underdog, -favorite)
 * @param marketSpreadUnderdog - Market spread from underdog perspective (always positive)
 * @returns 'FAV' or 'DOG'
 * 
 * Rule:
 *   If model_spread > market_spread → Sharp side = UNDERDOG (model says dog should get MORE points = dog undervalued)
 *   If model_spread < market_spread → Sharp side = FAVORITE (model says dog should get LESS points = fav undervalued)
 */
export function determineSharpSide(
  modelSpread: number,
  marketSpreadUnderdog: number
): SharpSideCode {
  if (modelSpread > marketSpreadUnderdog) {
    // Model expects smaller loss for underdog than market prices
    // → Underdog should be getting MORE points than they are
    // → Underdog is UNDERVALUED
    // → Sharp side = UNDERDOG
    return 'DOG';
  } else {
    // Model expects bigger loss for underdog than market prices
    // → Underdog is getting TOO MANY points
    // → Favorite is UNDERVALUED
    // → Sharp side = FAVORITE
    return 'FAV';
  }
}

/**
 * Format a spread value with sign
 */
function formatSpread(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`;
}

/**
 * Calculate complete spread context with team labels and sharp side
 * 
 * @param homeTeam - Home team name
 * @param awayTeam - Away team name
 * @param marketSpreadHome - Market spread from HOME team perspective (negative = home favored)
 * @param modelSpread - Signed model spread (+underdog, -favorite)
 * @returns SpreadContext with all required display strings
 * 
 * @example
 * calculateSpreadContext("Knicks", "Hawks", -5.5, 12.3)
 * // Returns context showing:
 * // - Market: Hawks +5.5
 * // - Model: Hawks +12.3
 * // - Sharp Side: Knicks -5.5
 */
export function calculateSpreadContext(
  homeTeam: string,
  awayTeam: string,
  marketSpreadHome: number,
  modelSpread: number
): SpreadContext {
  // Calculate away spread (always opposite of home)
  const marketSpreadAway = -marketSpreadHome;
  
  // Determine market favorite/underdog
  let marketFavorite: string;
  let marketUnderdog: string;
  let marketSpreadUnderdog: number;
  let marketSpreadFavorite: number;
  
  if (marketSpreadHome < 0) {
    // Home team is favorite
    marketFavorite = homeTeam;
    marketUnderdog = awayTeam;
    marketSpreadUnderdog = marketSpreadAway;  // Positive
    marketSpreadFavorite = marketSpreadHome;  // Negative
  } else {
    // Away team is favorite
    marketFavorite = awayTeam;
    marketUnderdog = homeTeam;
    marketSpreadUnderdog = marketSpreadHome;  // Positive
    marketSpreadFavorite = marketSpreadAway;  // Negative
  }
  
  // Determine sharp side using LOCKED RULE
  const sharpSide = determineSharpSide(modelSpread, marketSpreadUnderdog);
  
  // Calculate edge
  const edgePoints = Math.abs(modelSpread - marketSpreadUnderdog);
  
  // Determine sharp side team and line
  let sharpSideTeam: string;
  let sharpSideLine: number;
  let edgeDirection: SharpSideCode;
  
  if (sharpSide === 'FAV') {
    sharpSideTeam = marketFavorite;
    sharpSideLine = marketSpreadFavorite;
    edgeDirection = 'FAV';
  } else {
    sharpSideTeam = marketUnderdog;
    sharpSideLine = marketSpreadUnderdog;
    edgeDirection = 'DOG';
  }
  
  // Build display strings (MANDATORY)
  const marketSpreadDisplay = `${marketUnderdog} ${formatSpread(marketSpreadUnderdog)}`;
  const modelSpreadDisplay = `${marketUnderdog} ${formatSpread(modelSpread)}`;
  const sharpSideDisplay = `${sharpSideTeam} ${formatSpread(sharpSideLine)}`;
  
  return {
    homeTeam,
    awayTeam,
    marketSpreadHome,
    marketSpreadAway,
    modelSpread,
    marketFavorite,
    marketUnderdog,
    sharpSide,
    sharpSideTeam,
    sharpSideLine,
    marketSpreadDisplay,
    modelSpreadDisplay,
    sharpSideDisplay,
    edgePoints,
    edgeDirection,
  };
}

/**
 * Get reasoning text for why this sharp side was selected
 */
export function getSharpSideReasoning(context: SpreadContext): string {
  if (context.sharpSide === 'DOG') {
    return `Model projects ${context.marketUnderdog} to lose by less (${Math.abs(context.modelSpread).toFixed(1)} pts) than market prices (${Math.abs(context.marketSpreadHome).toFixed(1)} pts). Underdog getting too few points → Take the dog.`;
  } else {
    return `Model projects ${context.marketUnderdog} to lose by more (${Math.abs(context.modelSpread).toFixed(1)} pts) than market prices (${Math.abs(context.marketSpreadHome).toFixed(1)} pts). Underdog getting too many points → Fade the dog.`;
  }
}

/**
 * Get confidence descriptor for edge magnitude
 */
export function getEdgeConfidenceLevel(edgePoints: number): {
  level: 'HIGH' | 'MEDIUM' | 'LOW';
  label: string;
  description: string;
} {
  if (edgePoints >= 6.0) {
    return {
      level: 'HIGH',
      label: 'Strong Edge',
      description: `${edgePoints.toFixed(1)}pt edge — high confidence`
    };
  } else if (edgePoints >= 3.0) {
    return {
      level: 'MEDIUM',
      label: 'Moderate Edge',
      description: `${edgePoints.toFixed(1)}pt edge — medium confidence`
    };
  } else {
    return {
      level: 'LOW',
      label: 'Small Edge',
      description: `${edgePoints.toFixed(1)}pt edge — consider waiting for better number`
    };
  }
}

/**
 * Format spread context for display in UI cards
 * Returns array of display rows
 */
export function formatSpreadForDisplay(context: SpreadContext): {
  market: { label: string; value: string };
  model: { label: string; value: string };
  sharpSide: { label: string; value: string; highlight: boolean };
  edge: { label: string; value: string };
  reasoning: string;
} {
  return {
    market: {
      label: 'Market Spread',
      value: context.marketSpreadDisplay
    },
    model: {
      label: 'Model Spread',
      value: context.modelSpreadDisplay
    },
    sharpSide: {
      label: '🎯 Sharp Side',
      value: context.sharpSideDisplay,
      highlight: true
    },
    edge: {
      label: 'Edge',
      value: `${context.edgePoints.toFixed(1)} pts`
    },
    reasoning: getSharpSideReasoning(context)
  };
}

/**
 * Validate spread inputs before processing
 */
export function validateSpreadInputs(
  modelSpread: number | null | undefined,
  marketSpread: number | null | undefined
): { isValid: boolean; error?: string } {
  if (modelSpread === null || modelSpread === undefined) {
    return { isValid: false, error: 'Model spread is missing' };
  }
  
  if (marketSpread === null || marketSpread === undefined) {
    return { isValid: false, error: 'Market spread is missing' };
  }
  
  if (Math.abs(marketSpread) > 50) {
    return { isValid: false, error: `Market spread ${marketSpread} seems invalid (>50 points)` };
  }
  
  if (Math.abs(modelSpread) > 50) {
    return { isValid: false, error: `Model spread ${modelSpread} seems invalid (>50 points)` };
  }
  
  return { isValid: true };
}

/**
 * Quick helper to get sharp side from raw values
 * Use when you don't need full context
 */
export function getQuickSharpSide(
  homeTeam: string,
  awayTeam: string,
  marketSpreadHome: number,
  modelSpread: number
): { team: string; line: string; side: SharpSideCode } {
  const context = calculateSpreadContext(homeTeam, awayTeam, marketSpreadHome, modelSpread);
  return {
    team: context.sharpSideTeam,
    line: formatSpread(context.sharpSideLine),
    side: context.sharpSide
  };
}
