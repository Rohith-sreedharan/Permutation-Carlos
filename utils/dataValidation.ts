/**
 * Data Validation Utilities
 * 
 * CRITICAL: Validates that team labels, spread signs, and win probabilities
 * are internally consistent before rendering to prevent UI bugs.
 * 
 * If validation fails, blocks rendering with 'DATA MISMATCH — HOLD' message.
 */

export interface CanonicalTeamData {
  home_team: {
    name: string;
    team_id: string;
    win_probability: number;
    role: 'favorite' | 'underdog';
    vegas_spread: number;
  };
  away_team: {
    name: string;
    team_id: string;
    win_probability: number;
    role: 'favorite' | 'underdog';
    vegas_spread: number;
  };
  vegas_favorite: {
    name: string;
    spread: number;
    win_probability: number;
  };
  vegas_underdog: {
    name: string;
    spread: number;
    win_probability: number;
  };
  model_spread_home_perspective: number;
  vegas_spread_home_perspective: number;
}

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * Validates canonical team data integrity
 * 
 * Checks:
 * 1. Spread signs are consistent (favorite negative, underdog positive)
 * 2. Win probabilities sum to ~1.0
 * 3. Favorite has higher win probability than underdog
 * 4. Team roles match spread signs
 */
export function validateCanonicalTeamData(
  canonical: CanonicalTeamData
): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Rule 1: Vegas favorite spread must be negative
  if (canonical.vegas_favorite.spread >= 0) {
    errors.push(`Vegas favorite spread must be negative, got ${canonical.vegas_favorite.spread}`);
  }

  // Rule 2: Vegas underdog spread must be positive
  if (canonical.vegas_underdog.spread <= 0) {
    errors.push(`Vegas underdog spread must be positive, got ${canonical.vegas_underdog.spread}`);
  }

  // Rule 3: Spread magnitudes must match
  const favSpreadAbs = Math.abs(canonical.vegas_favorite.spread);
  const dogSpreadAbs = Math.abs(canonical.vegas_underdog.spread);
  if (Math.abs(favSpreadAbs - dogSpreadAbs) > 0.1) {
    errors.push(`Spread magnitudes don't match: favorite ${favSpreadAbs} vs underdog ${dogSpreadAbs}`);
  }

  // Rule 4: Win probabilities must sum to ~1.0
  const totalProb = canonical.home_team.win_probability + canonical.away_team.win_probability;
  if (Math.abs(totalProb - 1.0) > 0.01) {
    errors.push(`Win probabilities don't sum to 1.0: ${totalProb.toFixed(4)}`);
  }

  // Rule 5: Favorite must have higher win probability than underdog
  if (canonical.vegas_favorite.win_probability < canonical.vegas_underdog.win_probability) {
    warnings.push(
      `Favorite win probability (${(canonical.vegas_favorite.win_probability * 100).toFixed(1)}%) ` +
      `lower than underdog (${(canonical.vegas_underdog.win_probability * 100).toFixed(1)}%)`
    );
  }

  // Rule 6: Home spread sign must match role
  if (canonical.home_team.role === 'favorite' && canonical.home_team.vegas_spread >= 0) {
    errors.push(`Home team is favorite but has positive spread: ${canonical.home_team.vegas_spread}`);
  }
  if (canonical.home_team.role === 'underdog' && canonical.home_team.vegas_spread <= 0) {
    errors.push(`Home team is underdog but has negative spread: ${canonical.home_team.vegas_spread}`);
  }

  // Rule 7: Away spread must be opposite of home spread
  const spreadSum = canonical.home_team.vegas_spread + canonical.away_team.vegas_spread;
  if (Math.abs(spreadSum) > 0.1) {
    errors.push(`Home and away spreads don't sum to zero: ${spreadSum.toFixed(2)}`);
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings
  };
}

/**
 * Validates simulation data before rendering
 * 
 * Returns validation result with errors that should block rendering
 */
export function validateSimulationData(simulation: any, event: any): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Check if canonical team data exists
  if (!simulation.canonical_teams) {
    warnings.push('Legacy simulation detected - missing canonical team data');
    return { isValid: true, errors, warnings }; // Allow legacy data
  }

  const canonical = simulation.canonical_teams as CanonicalTeamData;

  // Validate canonical data integrity
  const canonicalValidation = validateCanonicalTeamData(canonical);
  errors.push(...canonicalValidation.errors);
  warnings.push(...canonicalValidation.warnings);

  // Validate team names match event
  if (canonical.home_team.name !== simulation.team_a) {
    errors.push(`Canonical home team (${canonical.home_team.name}) doesn't match team_a (${simulation.team_a})`);
  }
  if (canonical.away_team.name !== simulation.team_b) {
    errors.push(`Canonical away team (${canonical.away_team.name}) doesn't match team_b (${simulation.team_b})`);
  }

  // Validate win probabilities match canonical
  const team_a_prob_diff = Math.abs(simulation.team_a_win_probability - canonical.home_team.win_probability);
  if (team_a_prob_diff > 0.01) {
    errors.push(
      `team_a_win_probability (${simulation.team_a_win_probability.toFixed(4)}) ` +
      `doesn't match canonical (${canonical.home_team.win_probability.toFixed(4)})`
    );
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings
  };
}

/**
 * Get spread display string with correct sign and team
 * 
 * Uses canonical data to ensure correct team label and spread sign
 */
export function getSpreadDisplay(canonical: CanonicalTeamData, teamName: string): string {
  if (canonical.home_team.name === teamName) {
    const spread = canonical.home_team.vegas_spread;
    return spread < 0 ? `${teamName} ${spread.toFixed(1)}` : `${teamName} +${spread.toFixed(1)}`;
  } else if (canonical.away_team.name === teamName) {
    const spread = canonical.away_team.vegas_spread;
    return spread < 0 ? `${teamName} ${spread.toFixed(1)}` : `${teamName} +${spread.toFixed(1)}`;
  }
  return `${teamName} (ERROR)`;
}

/**
 * Get win probability for a specific team
 * 
 * Uses canonical binding to prevent team label flips
 */
export function getTeamWinProbability(canonical: CanonicalTeamData, teamName: string): number {
  if (canonical.home_team.name === teamName) {
    return canonical.home_team.win_probability;
  } else if (canonical.away_team.name === teamName) {
    return canonical.away_team.win_probability;
  }
  return 0.5; // Fallback
}
