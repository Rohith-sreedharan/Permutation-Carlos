/**
 * Edge Validation System - 7-Rule Framework
 * 
 * An EDGE is only shown when ALL 7 rules pass.
 * If any rule fails, classify as "LEAN" instead.
 * 
 * This applies to ALL sports: NBA, NCAAB, NFL, NCAAF, NHL, MLB
 */

export interface EdgeValidationInput {
  win_probability: number;        // 0.0 - 1.0
  implied_probability: number;    // From odds: 1 / (decimal_odds)
  confidence: number;             // 0-100 scale (normalized)
  volatility: string;             // 'low' | 'moderate' | 'high'
  sim_count: number;              // Number of simulations run
  expected_value: number;         // EV percentage
  distribution_favor: number;     // 0.0 - 1.0 (% of sims favoring side)
  injury_impact: number;          // Total injury impact in points
  model_spread?: number;          // Model's predicted spread (optional)
}

export interface EdgeValidationResult {
  is_valid_edge: boolean;
  classification: 'EDGE' | 'LEAN' | 'NEUTRAL';
  failed_rules: string[];
  passed_rules: string[];
  total_rules: number;
  confidence_level: 'HIGH' | 'MODERATE' | 'LOW';
  recommendation: string;
  summary: string;
}

/**
 * Validate if a projection qualifies as an EDGE
 * 
 * Primary Classification (overrides 7-rule system):
 * - STRONG EDGE: Win probability ≥ 70% AND spread ≥ 3 points
 * - MODERATE LEAN: Win probability 55-69%
 * - NEUTRAL: Win probability 48-52%
 * 
 * 7-Rule Validation (applied when primary classification doesn't trigger):
 * 1. Win probability ≥ 5% above implied probability
 * 2. Confidence ≥ 60
 * 3. Volatility not HIGH
 * 4. Sim Power ≥ 25K
 * 5. EV positive
 * 6. Distribution favors side ≥ 58%
 * 7. Injury impact stable (<1.5)
 */
export function validateEdge(input: EdgeValidationInput): EdgeValidationResult {
  const failed_rules: string[] = [];
  const passed_rules: string[] = [];

  // PRIMARY CLASSIFICATION (overrides 7-rule system for clear edges)
  // This ensures 86% win probability shows as STRONG EDGE, not MODERATE LEAN
  const winProb = input.win_probability;
  const spread = Math.abs(input.model_spread || 0);
  
  let primaryClassification: 'EDGE' | 'LEAN' | 'NEUTRAL' | null = null;
  
  // STRONG EDGE: Win probability ≥ 70% AND spread ≥ 3 points
  if (winProb >= 0.70 && spread >= 3) {
    primaryClassification = 'EDGE';
  }
  // MODERATE LEAN: Win probability 55-69%
  else if (winProb >= 0.55 && winProb < 0.70) {
    primaryClassification = 'LEAN';
  }
  // NEUTRAL: Win probability 48-52%
  else if (winProb >= 0.48 && winProb <= 0.52) {
    primaryClassification = 'NEUTRAL';
  }

  // Rule 1: Win probability ≥ 5% above implied
  const prob_edge = input.win_probability - input.implied_probability;
  if (prob_edge >= 0.05) {
    passed_rules.push('Win probability +5% above market');
  } else {
    failed_rules.push(`Win prob edge only +${(prob_edge * 100).toFixed(1)}% (need +5%)`);
  }

  // Rule 2: Confidence ≥ 60
  if (input.confidence >= 60) {
    passed_rules.push('Confidence ≥ 60');
  } else {
    failed_rules.push(`Confidence ${input.confidence}/100 (need ≥60)`);
  }

  // Rule 3: Volatility not HIGH
  if (input.volatility.toLowerCase() !== 'high') {
    passed_rules.push('Volatility acceptable');
  } else {
    failed_rules.push('Volatility is HIGH (unstable)');
  }

  // Rule 4: Sim Power ≥ 25K
  if (input.sim_count >= 25000) {
    passed_rules.push(`Sim power sufficient (${(input.sim_count / 1000).toFixed(0)}K)`);
  } else {
    failed_rules.push(`Sim count ${(input.sim_count / 1000).toFixed(0)}K (need ≥25K)`);
  }

  // Rule 5: EV positive
  if (input.expected_value > 0) {
    passed_rules.push('Expected value positive');
  } else {
    failed_rules.push(`EV ${input.expected_value.toFixed(2)}% (need >0)`);
  }

  // Rule 6: Distribution favors side ≥ 58%
  if (input.distribution_favor >= 0.58) {
    passed_rules.push(`Distribution ${(input.distribution_favor * 100).toFixed(0)}% favors`);
  } else {
    failed_rules.push(`Distribution ${(input.distribution_favor * 100).toFixed(0)}% (need ≥58%)`);
  }

  // Rule 7: Injury impact stable (<1.5)
  if (Math.abs(input.injury_impact) < 1.5) {
    passed_rules.push('Injury impact stable');
  } else {
    failed_rules.push(`Injury impact ${Math.abs(input.injury_impact).toFixed(1)} pts (need <1.5)`);
  }

  // Determine classification
  // Use primary classification if triggered, otherwise use 7-rule system
  const is_valid_edge = failed_rules.length === 0 || primaryClassification === 'EDGE';
  const classification = primaryClassification || 
                         (is_valid_edge ? 'EDGE' : 
                          passed_rules.length >= 5 ? 'LEAN' : 
                          'NEUTRAL');

  // Confidence level based on rules passed
  const confidence_level = passed_rules.length === 7 ? 'HIGH' :
                           passed_rules.length >= 5 ? 'MODERATE' :
                           'LOW';

  // Generate recommendation
  let recommendation = '';
  let summary = '';
  
  if (classification === 'EDGE') {
    if (primaryClassification === 'EDGE') {
      recommendation = `🔥 STRONG EDGE detected. Win probability ${(winProb * 100).toFixed(1)}% with ${spread.toFixed(1)} point spread. High-conviction scenario.`;
      summary = `Strong quantitative edge with ${(winProb * 100).toFixed(1)}% win probability and ${spread.toFixed(1)} point model spread. Market appears mispriced.`;
    } else {
      recommendation = `🔥 Valid EDGE detected. All 7 criteria met. High-conviction scenario.`;
      summary = `Strong quantitative edge with ${passed_rules.length}/7 validation rules passed. Model confidence high, volatility acceptable, sufficient simulation depth.`;
    }
  } else if (classification === 'LEAN') {
    recommendation = `⚡ Moderate LEAN identified. ${passed_rules.length}/7 rules passed. Use conservative sizing.`;
    summary = `Partial edge with ${passed_rules.length}/7 rules met. Consider soft exposure with reduced unit sizing. Failed criteria: ${failed_rules.map(r => r.split(' ')[0]).join(', ')}.`;
  } else {
    recommendation = `⚠️ NEUTRAL projection. Insufficient edge criteria (${passed_rules.length}/7 passed). Avoid action.`;
    summary = `No actionable edge detected. Only ${passed_rules.length}/7 validation rules passed. Market appears efficiently priced. Recommend passing on this opportunity.`;
  }

  return {
    is_valid_edge,
    classification,
    failed_rules,
    passed_rules,
    total_rules: 7,
    confidence_level,
    recommendation,
    summary
  };
}

/**
 * Calculate implied probability from American odds
 */
export function getImpliedProbability(american_odds: number): number {
  if (american_odds > 0) {
    return 100 / (american_odds + 100);
  } else {
    return Math.abs(american_odds) / (Math.abs(american_odds) + 100);
  }
}

/**
 * Detect garbage time scenario (NBA only)
 * Returns true if game is likely to have garbage time volatility
 */
export function detectGarbageTime(
  margin: number,
  time_remaining_pct: number,
  score_volatility: number
): boolean {
  // Garbage time criteria:
  // 1. Margin > 15 points with < 25% time remaining
  // 2. Margin > 20 points with < 50% time remaining
  // 3. High volatility (>150) in blowout scenario

  if (margin > 20 && time_remaining_pct < 0.5) return true;
  if (margin > 15 && time_remaining_pct < 0.25) return true;
  if (margin > 12 && score_volatility > 150) return true;

  return false;
}

/**
 * Generate "Why This Edge Exists" explanation
 */
export function explainEdgeSource(
  edge_validation: EdgeValidationResult,
  factors: {
    pace_factor?: number;
    injury_impact?: number;
    rest_advantage?: number;
    matchup_rating?: number;
    market_inefficiency?: number;
  }
): {
  explanation: string;
  factors: Array<{type: string; description: string; impact: 'HIGH' | 'MEDIUM' | 'LOW'}>;
  market_inefficiency: string;
} {
  if (!edge_validation.is_valid_edge) {
    return {
      explanation: "No valid edge detected. Market appears efficiently priced.",
      factors: [],
      market_inefficiency: "Market pricing appears efficient with no significant model divergence"
    };
  }

  const explanations: string[] = [];
  const edgeFactors: Array<{type: string; description: string; impact: 'HIGH' | 'MEDIUM' | 'LOW'}> = [];

  // Pace-based edge
  if (factors.pace_factor && Math.abs(factors.pace_factor - 1.0) > 0.05) {
    if (factors.pace_factor > 1.0) {
      explanations.push(`Fast-paced game (+${((factors.pace_factor - 1) * 100).toFixed(1)}%) favors higher-scoring outcome`);
      edgeFactors.push({
        type: 'Pace',
        description: `${((factors.pace_factor - 1) * 100).toFixed(1)}% faster than league average`,
        impact: factors.pace_factor > 1.1 ? 'HIGH' : 'MEDIUM'
      });
    } else {
      explanations.push(`Slow tempo (${((factors.pace_factor - 1) * 100).toFixed(1)}%) suppresses scoring expectations`);
      edgeFactors.push({
        type: 'Pace',
        description: `${Math.abs((factors.pace_factor - 1) * 100).toFixed(1)}% slower than average`,
        impact: factors.pace_factor < 0.9 ? 'HIGH' : 'MEDIUM'
      });
    }
  }

  // Injury-based edge
  if (factors.injury_impact && Math.abs(factors.injury_impact) > 0.5) {
    explanations.push(`Key injuries shift expected margin by ${Math.abs(factors.injury_impact).toFixed(1)} points`);
    edgeFactors.push({
      type: 'Injuries',
      description: `${Math.abs(factors.injury_impact).toFixed(1)} point impact from key absences`,
      impact: Math.abs(factors.injury_impact) > 2 ? 'HIGH' : 'MEDIUM'
    });
  }

  // Rest advantage
  if (factors.rest_advantage && Math.abs(factors.rest_advantage) > 0) {
    explanations.push(`Rest differential provides ${factors.rest_advantage > 0 ? 'advantage' : 'disadvantage'} in fatigue metrics`);
    edgeFactors.push({
      type: 'Rest',
      description: `${Math.abs(factors.rest_advantage)} day advantage`,
      impact: 'LOW'
    });
  }

  // Matchup rating
  if (factors.matchup_rating && factors.matchup_rating !== 0.5) {
    if (factors.matchup_rating > 0.6) {
      explanations.push(`Favorable matchup rating (${(factors.matchup_rating * 100).toFixed(0)}%) based on historical head-to-head`);
      edgeFactors.push({
        type: 'Matchup',
        description: `${(factors.matchup_rating * 100).toFixed(0)}% favorable historical profile`,
        impact: factors.matchup_rating > 0.7 ? 'HIGH' : 'MEDIUM'
      });
    } else if (factors.matchup_rating < 0.4) {
      explanations.push(`Unfavorable matchup dynamics (${(factors.matchup_rating * 100).toFixed(0)}%) suggest contrarian value`);
      edgeFactors.push({
        type: 'Matchup',
        description: `Contrarian opportunity at ${(factors.matchup_rating * 100).toFixed(0)}%`,
        impact: 'MEDIUM'
      });
    }
  }

  // Market inefficiency
  let inefficiency_text = "No significant market mispricing detected";
  if (factors.market_inefficiency && Math.abs(factors.market_inefficiency) > 2) {
    explanations.push(`Market appears ${Math.abs(factors.market_inefficiency).toFixed(1)} points mispriced based on sim distribution`);
    inefficiency_text = `Model diverges ${Math.abs(factors.market_inefficiency).toFixed(1)} points from consensus, suggesting bookmaker undervaluation`;
    edgeFactors.push({
      type: 'Market Gap',
      description: `${Math.abs(factors.market_inefficiency).toFixed(1)} point misprice detected`,
      impact: Math.abs(factors.market_inefficiency) > 4 ? 'HIGH' : 'MEDIUM'
    });
  }

  const finalExplanation = explanations.length > 0 
    ? explanations.join('. ') + '.'
    : "Edge derives from statistical model convergence across multiple simulation clusters.";

  return {
    explanation: finalExplanation,
    factors: edgeFactors,
    market_inefficiency: inefficiency_text
  };
}
