// FIX: Added 'leaderboard', 'profile', 'billing', 'earnings', 'admin' to support more pages
export type Page = 'dashboard' | 'community' | 'trust-loop' | 'architect' | 'daily-cards' | 'affiliates' | 'leaderboard' | 'profile' | 'wallet' | 'billing' | 'earnings' | 'settings' | 'telegram' | 'gameDetail' | 'onboarding' | 'war-room' | 'war-room-leaderboard' | 'admin';

export interface Bet {
  type: 'Moneyline' | 'Spread' | 'Total';
  pick: string;
  value: string;
}

// Player-specific prop mispricing data
export interface PropMispricing {
  player_name: string;
  position: string; // Exact position (PG, SG, SF, PF, C, QB, RB, WR, etc.)
  team: string;
  market: string; // "Assists", "Points", "Rebounds", "Passing Yards", etc.
  line: number;
  win_probability: number;
  expected_value: number;
  confidence: number;
  // Performance context
  recent_avg?: number; // Last 5 games average
  season_avg?: number;
  minutes_projection?: number;
  opponent_rank?: number; // Opponent defensive rank vs position
  // Simulation data for drill-down
  distribution?: Array<{ value: number; probability: number }>;
  confidence_range?: [number, number]; // 95% CI
  scenario_factors?: string[]; // e.g., ["Pace-up matchup", "High usage rate"]
}

export interface Event {
  id: string;
  sport_key: string;
  commence_time: string;
  local_date_est?: string; // EST date for display
  home_team: string;
  away_team: string;
  bets: Bet[];
  top_prop_bet: string;
  // Player-specific props (replaces generic position labels)
  top_prop_mispricings?: PropMispricing[];
}

export interface Prediction {
  event_id: string;
  confidence: number;
  recommended_bet?: string | null;
  ev_percent?: number;
  volatility?: string;
  outcome_probabilities?: Record<string, number>;
  sharp_money_indicator?: number;
  correlation_score?: number;
}

export interface EventWithPrediction extends Event {
    prediction?: Prediction;
}

export interface User {
    id: string;
    rank: number;
    username: string;
    avatarUrl: string;
    score: number;
    streaks: number;
  plan_id?: 'telegram_syndicate' | 'beatvegas_platform' | null;
  platform_access?: boolean;
  telegram_access?: boolean;
    is_affiliate?: boolean; // For creator status
}

export interface ChatMessage {
    id: string;
    user: {
        username: string;
        avatarUrl: string;
        is_admin?: boolean;
    };
    message: string;
    timestamp: string;
    announcement?: boolean;
}

// Beat Vegas - Monte Carlo Simulation Types
export interface MonteCarloSimulation {
  simulation_id: string;
  event_id: string;
  iterations: number;
  team_a: string;
  team_b: string;
  team_a_win_probability: number;
  team_b_win_probability: number;
  avg_team_a_score: number;
  avg_team_b_score: number;
  avg_margin: number;
  avg_total?: number;
  avg_total_score?: number;
  over_probability?: number;
  under_probability?: number;
  total_line?: number;
  spread?: number; // Vegas spread line
  volatility_index: number | string;
  volatility_score?: number;
  volatility?: string;
  confidence_score: number;
  pick_state?: 'PICK' | 'LEAN' | 'AVOID' | 'PASS' | 'UNKNOWN'; // Truth Mode state
  status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'CACHED' | 'PRICE_MOVED' | 'INVALIDATED' | 'FAILED';
  simulation_mode?: 'BASELINE';  // Team-level model (default/normal operation)
  confidence_penalty?: number;  // Applied penalty for data quality
  message?: string;
  can_publish?: boolean;
  can_parlay?: boolean;
  outcome?: {
    recommended_bet?: string | null;
    confidence?: number;
    expected_value_percent?: number;
  };
  spread_distribution?: Record<string, number> | Array<{ margin: number; probability: number }>;
  total_distribution?: Record<string, number> | Array<{ total: number; probability: number }>;
  score_distribution?: Array<{
    home_score: number;
    away_score: number;
    probability: number;
  }>;
  variance?: number;
  win_probability?: number;
  // Canonical team anchor data (prevents UI bugs)
  canonical_teams?: {
    home_team: {
      name: string;
      team_id: string;
      vegas_spread: number;
      win_probability: number;
    };
    away_team: {
      name: string;
      team_id: string;
      vegas_spread: number;
      win_probability: number;
    };
    vegas_favorite: {
      name: string;
      team_id: string;
      spread: number;
    };
    vegas_underdog: {
      name: string;
      team_id: string;
      spread: number;
    };
    model_spread_home_perspective: number;
  };
  injury_impact?: Array<{
    player: string;
    team: string;
    status: string;
    impact_points: number;
  }>;
  top_props?: Array<{
    player: string;
    prop_type: string;
    line: number;
    probability: number;
    ev: number;
    edge?: number;
    ai_projection?: number;
  }>;
  confidence_intervals?: {
    ci_68: [number, number];
    ci_95: [number, number];
    ci_99: [number, number];
  };
  // Metadata
  metadata?: {
    user_tier?: string;
    iterations_run?: number;
    sim_count_used?: number;
    variance?: number;
    ci_95?: [number, number];
    precision_level?: string;
    confidence_interval_width?: number;
    cached?: boolean;
    simulation_created_at?: string;
    generated_at?: string;
  };
  // Market context - enhanced with timestamp for backtesting
  market_context?: {
    total_line?: number;
    spread?: number;
    bookmaker_source?: string;
    odds_timestamp?: string;
    sim_result_delta?: number;
    edge_percentage?: number;
  };
  // Pace and projections
  pace_factor?: number;
  projected_score?: number;
  vegas_line?: number;
  // Injury summary
  injury_summary?: {
    total_offensive_impact?: number;
    total_defensive_impact?: number;
    combined_net_impact?: number;
    impact_description?: string;
    key_injuries?: Array<{
      player: string;
      team: string;
      position: string;
      status: string;
    }>;
  };
  created_at: string;
  // Sharp Analysis - Model vs Vegas
  sharp_analysis?: {
    probabilities?: {
      p_cover_home: number;
      p_cover_away: number;
      p_win_home: number;
      p_win_away: number;
      p_over: number;
      p_under: number;
      validator_status?: 'PASS' | 'FAIL';
      validator_errors?: string[];
    };
    total?: {
      has_edge: boolean;
      vegas_total: number;
      model_total: number;
      market_total?: number;
      edge_points: number;
      edge_direction: 'OVER' | 'UNDER';
      sharp_side: 'OVER' | 'UNDER';
      sharp_market?: string;
      sharp_selection?: string;
      edge_grade: 'S' | 'A' | 'B' | 'C' | 'D' | 'F';
      sharp_side_display: string;
      sharp_side_reason?: string;
      edge_reasoning?: {
        primary_factor: string;
        contributing_factors: string[];
        model_reasoning: string;
        market_positioning: string;
        contrarian_indicator: boolean;
        confidence_level: 'HIGH' | 'MEDIUM' | 'LOW';
        // CRITICAL: Structured quantitative data for backtesting
        structured_data?: {
          injury_impact_points: number;
          pace_adjustment_percent: number;
          variance_sigma: number;
          convergence_score: number;
          median_sim_total: number;
          vegas_total: number;
          delta_vs_vegas: number;
          contrarian: boolean;
          confidence_numeric: number;
          confidence_bucket: 'HIGH' | 'MEDIUM' | 'LOW';
          primary_factor: string;
          primary_factor_impact_pts: number;
          factor_contributions: Array<{
            factor: string;
            impact_points: number;
            contribution_pct: number;
            note?: string;
          }>;
          residual_unexplained_pts: number;
          risk_factors: Array<{
            risk: string;
            severity: 'HIGH' | 'MEDIUM' | 'LOW';
            description: string;
          }>;
          overall_risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
          backtest_ready: boolean;
          calibration_bucket: string;
          edge_grade_numeric: number;
        };
      };
    };
    spread?: {
      has_edge: boolean;
      vegas_spread: number;
      model_spread: number;
      market_spread_home?: number;
      edge_points: number;
      edge_direction: 'FAV' | 'DOG';
      sharp_side: 'FAV' | 'DOG';
      sharp_market?: string;
      sharp_selection?: string;
      sharp_action?: string;  // NEW: Gap-based sharp side action (TAKE_POINTS, TAKE_POINTS_LIVE, LAY_POINTS, NO_SHARP_PLAY)
      edge_grade: 'S' | 'A' | 'B' | 'C' | 'D' | 'F';
      sharp_side_display: string;
      sharp_side_reason?: string;
      recommended_bet?: string;  // NEW: Human-readable bet recommendation
      edge_after_penalty?: number;  // NEW: Edge after volatility penalty
      reasoning?: string;  // NEW: Detailed reasoning for sharp action
    };
    moneyline?: {
      has_edge: boolean;
      sharp_market?: string;
      sharp_selection?: string;
      edge_pct?: number;
    };
    model_line_display?: string;
    vegas_line_display?: string;
    sharp_side_display?: string;
    edge_points_display?: string;
    debug_payload?: any;
    disclaimer: string;
  };
}

// Risk Profile & Decision Capital
export interface RiskProfile {
  user_id: string;
  starting_capital: number;
  unit_strategy: 'fixed' | 'percentage'; // Fixed dollar amount or % of capital
  unit_size: number; // Dollar amount or percentage (1-5%)
  risk_classification: 'conservative' | 'balanced' | 'aggressive';
  // Calculated fields
  suggested_exposure_per_decision?: number;
  volatility_tolerance?: number;
  max_daily_exposure?: number;
  // Performance tracking
  total_decisions?: number;
  winning_decisions?: number;
  roi?: number;
  sharpe_ratio?: number;
}

export interface DecisionLog {
  decision_id: string;
  user_id: string;
  event_id: string;
  player_name?: string; // For prop decisions
  market: string;
  line: number;
  confidence_weight: number; // 1-5 units based on win probability
  exposure: number; // Dollar amount of decision
  expected_value: number;
  win_probability: number;
  decision_time: string;
  // Resolution
  outcome?: 'win' | 'loss' | 'push' | 'pending';
  actual_result?: number;
  profit_loss?: number;
  // Alignment tracking
  aligned_with_model: boolean; // Did user follow high-confidence forecast?
}

// Beat Vegas - CLV Tracking Types
export interface CLVDataPoint {
  event_id: string;
  pick_date: string;
  sport: string;
  team: string;
  predicted_prob: number;
  market_prob: number;
  clv: number;
  outcome?: 'win' | 'loss' | 'pending';
}

export interface CLVStats {
  average_clv: number;
  total_picks: number;
  positive_clv_picks: number;
  clv_trend: 'improving' | 'declining' | 'stable';
  last_30_days_avg: number;
}

// Beat Vegas - Performance Metrics Types
export interface PerformanceMetrics {
  brier_score: number;
  log_loss: number;
  roi: number;
  clv: number;
  total_picks: number;
  winning_picks: number;
  win_rate: number;
  avg_odds: number;
  profit_loss: number;
  market_breakdown: {
    [sport: string]: {
      picks: number;
      win_rate: number;
      roi: number;
      clv: number;
    };
  };
}

// Beat Vegas - Subscription Plan Types
export interface SubscriptionTier {
  id: 'telegram_syndicate' | 'beatvegas_platform';
  name: string;
  price: number;
  simulations: string;
  features: string[];
  cta: string;
  popular?: boolean;
}


export interface TopAnalyst {
    id: string;
    rank: number;
    username: string;
    avatarUrl: string;
    units: number;
}

export interface AffiliateStat {
    label: string;
    value: string;
    change: string;
    changeType: 'increase' | 'decrease';
}

export interface Referral {
    id: string;
    user: string;
    date_joined: string;
    status: 'Active' | 'Cancelled';
    commission: number;
}

export interface AuthResponse {
    access_token: string;
    token_type: string;
    requires_2fa?: boolean;
    temp_token?: string;
}

export interface UserCredentials {
    email: string;
    password: string;
}

export interface UserRegistration {
    email: string;
    username: string;
    password: string;
}

// ========================================
// CANONICAL MARKETVIEW SCHEMA (mv.v1)
// Singles Engine - Non-Negotiable Contract
// ========================================

export type IntegrityStatus = 'PASS' | 'DEGRADE' | 'FAIL';
export type EdgeClass = 'EDGE' | 'LEAN' | 'MARKET_ALIGNED' | 'NO_PLAY' | 'INVALID';
export type MarketType = 'SPREAD' | 'MONEYLINE' | 'TOTAL';
export type SelectionSide = 'HOME' | 'AWAY' | 'OVER' | 'UNDER';

/**
 * Individual selection within a market
 * REQUIRED: selection_id, side, market_probability, model_probability
 * CONDITIONALLY REQUIRED: market_line_for_selection (nullable only for MONEYLINE)
 */
export interface MarketSelection {
  selection_id: string; // REQUIRED: SHA-256(event_id|market_type|side|line|book)
  side: SelectionSide; // REQUIRED
  market_line_for_selection: number | null; // REQUIRED (null only for ML)
  model_fair_line_for_selection: number | null; // REQUIRED
  market_probability: number; // REQUIRED
  model_probability: number; // REQUIRED
  // OPTIONAL fields (never gate rendering)
  display_label?: string;
  tooltip?: string;
}

/**
 * Canonical MarketView - Single source of truth for frontend rendering
 * 
 * REQUIRED FIELDS (missing any = SAFE MODE):
 * - schema_version, event_id, market_type, snapshot_hash
 * - selections[2] with all required selection fields
 * - edge_class, model_preference_selection_id
 * - integrity_status
 * 
 * OPTIONAL FIELDS (never trigger SAFE MODE):
 * - labels, narratives, grades, tooltips, UI copy
 */
export interface MarketView {
  // REQUIRED: Schema versioning
  schema_version: string; // REQUIRED: "mv.v1"
  
  // REQUIRED: Identifiers
  event_id: string; // REQUIRED
  market_type: MarketType; // REQUIRED
  snapshot_hash: string; // REQUIRED: locks this render to one OddsAPI snapshot
  book_key?: string; // Book source for this market
  
  // REQUIRED: Integrity gates
  integrity_status: IntegrityStatus; // REQUIRED: PASS|DEGRADE|FAIL
  integrity_violations: string[]; // REQUIRED: empty array if PASS
  
  // REQUIRED: Selections (exactly 2)
  selections: [MarketSelection, MarketSelection]; // REQUIRED: tuple of 2
  
  // REQUIRED: Model preference & edge
  model_preference_selection_id: string | 'NO_EDGE' | 'INVALID'; // REQUIRED
  edge_class: EdgeClass; // REQUIRED
  edge_points: number; // REQUIRED
  
  // OPTIONAL: UI enhancements (never gate)
  ui_render_mode?: 'FULL' | 'SAFE'; // Derived from integrity_status
  explanation?: string; // Per-market explanation text
  grade?: 'S' | 'A' | 'B' | 'C' | 'D'; // Visual grade badge
  confidence_score?: number; // 0-100
  
  // OPTIONAL: Debug (dev toggle only)
  debug_payload?: Record<string, any>;
}

/**
 * CANONICAL DECISION OBJECT (Phase 1 Audit Requirement)
 * ======================================================
 * 
 * Single source of truth for all UI components displaying edge decisions.
 * This object MUST be read by:
 * - Top card classification
 * - Final Unified Summary
 * - Action Summary  
 * - Official Edge badge
 * - "Why This Edge Exists" section
 * 
 * NO UI COMPONENT may compute its own edge determination.
 * The OFFICIAL EDGE badge MUST only appear when:
 *   validator_status === 'PASS' AND edge_status === 'EDGE'
 * 
 * rules_passed is FROZEN at snapshot time - does not change between page loads.
 */
export type ValidatorStatus = 'PASS' | 'FAIL' | 'DEGRADED';
export type EdgeStatus = 'EDGE' | 'LEAN' | 'NO_EDGE' | 'BLOCKED';
export type OfficialAction = 'TAKE' | 'LEAN' | 'NO_ACTION' | 'BLOCKED';
export type OfficialMarket = 'SPREAD' | 'MONEYLINE' | 'TOTAL' | null;
export type OfficialSide = 'HOME' | 'AWAY' | 'OVER' | 'UNDER' | null;

export interface RulesPassed {
  gap_threshold: boolean;        // Model-market gap meets minimum
  confidence_threshold: boolean; // Confidence meets minimum
  volatility_check: boolean;     // Volatility within acceptable range
  integrity_check: boolean;      // Data integrity passes
  odds_alignment: boolean;       // Odds match at snapshot time
  staleness_check: boolean;      // Data not stale
}

export interface CanonicalDecision {
  // Identifiers
  event_id: string;
  snapshot_hash: string;
  
  // Engine decision (READ-ONLY)
  validator_status: ValidatorStatus;
  edge_status: EdgeStatus;
  
  // Official pick (null if NO_EDGE/BLOCKED)
  official_market: OfficialMarket;
  official_side: OfficialSide;
  official_action: OfficialAction;
  
  // Metrics frozen at decision time
  model_gap_pts: number;           // Frozen at snapshot
  win_probability_edge: number;    // Frozen at snapshot (0-1)
  
  // Rules that were checked (FROZEN - never recomputed)
  rules_passed: RulesPassed;
  
  // Reasons for this decision (pre-computed by engine)
  reasons: string[];
  
  // Block reason if blocked
  block_reason?: string;
  
  // Timestamp when decision was computed
  computed_at: string;
}

/**
 * Derive CanonicalDecision from MarketView (engine output)
 * UI MUST use this function - direct computation forbidden
 * 
 * FROZEN AT SNAPSHOT TIME: rules_passed are computed once from marketView
 * and never recomputed. The snapshot_hash locks all values to one odds snapshot.
 */
export function deriveCanonicalDecision(
  eventId: string,
  marketView: MarketView | null | undefined,
  marketType: 'SPREAD' | 'MONEYLINE' | 'TOTAL'
): CanonicalDecision | null {
  if (!marketView) return null;
  
  // Extract preferred selection
  const preferredSel = marketView.model_preference_selection_id !== 'NO_EDGE' && 
                       marketView.model_preference_selection_id !== 'INVALID'
    ? marketView.selections.find(s => s.selection_id === marketView.model_preference_selection_id)
    : null;
  
  // Determine official side
  let officialSide: OfficialSide = null;
  if (preferredSel) {
    officialSide = preferredSel.side as OfficialSide;
  }
  
  // Determine edge status from edge_class
  let edgeStatus: EdgeStatus;
  switch (marketView.edge_class) {
    case 'EDGE': edgeStatus = 'EDGE'; break;
    case 'LEAN': edgeStatus = 'LEAN'; break;
    case 'MARKET_ALIGNED': edgeStatus = 'NO_EDGE'; break;
    case 'NO_PLAY':
    case 'INVALID': edgeStatus = 'BLOCKED'; break;
    default: edgeStatus = 'NO_EDGE';
  }
  
  // Determine official action
  let officialAction: OfficialAction;
  if (edgeStatus === 'EDGE') officialAction = 'TAKE';
  else if (edgeStatus === 'LEAN') officialAction = 'LEAN';
  else if (edgeStatus === 'BLOCKED') officialAction = 'BLOCKED';
  else officialAction = 'NO_ACTION';
  
  // FROZEN AT SNAPSHOT TIME: Compute rules_passed from integrity checks
  // These values are locked to the marketView snapshot and never recomputed
  const rulesPassed: RulesPassed = {
    gap_threshold: marketView.edge_points >= 2.0,
    confidence_threshold: (marketView.confidence_score ?? 0) >= 50,
    volatility_check: !marketView.integrity_violations?.includes('HIGH_VOLATILITY'),
    integrity_check: marketView.integrity_status === 'PASS',
    odds_alignment: !marketView.integrity_violations?.includes('ODDS_MISMATCH'),
    staleness_check: !marketView.integrity_violations?.includes('STALE_DATA'),
  };
  
  // Win probability edge (frozen at snapshot)
  const modelProb = preferredSel?.model_probability ?? 0.5;
  const marketProb = preferredSel?.market_probability ?? 0.5;
  const winProbEdge = modelProb - marketProb;
  
  return {
    event_id: eventId,
    snapshot_hash: marketView.snapshot_hash,
    validator_status: marketView.integrity_status === 'PASS' ? 'PASS' : 
                      marketView.integrity_status === 'FAIL' ? 'FAIL' : 'DEGRADED',
    edge_status: edgeStatus,
    official_market: marketType,
    official_side: officialSide,
    official_action: officialAction,
    model_gap_pts: marketView.edge_points,
    win_probability_edge: winProbEdge,
    rules_passed: rulesPassed,
    reasons: marketView.explanation ? [marketView.explanation] : [],
    block_reason: marketView.integrity_violations?.join(', '),
    // Use snapshot_hash as a timestamp proxy since it's computed at decision time
    computed_at: `snapshot:${marketView.snapshot_hash}`,
  };
}

/**
 * Check if OFFICIAL EDGE badge should be shown
 * This is THE ONLY function that determines this - no other checks allowed
 */
export function shouldShowOfficialEdge(decision: CanonicalDecision | null): boolean {
  if (!decision) return false;
  return decision.validator_status === 'PASS' && decision.edge_status === 'EDGE';
}

/**
 * Complete simulation response with canonical MarketViews
 */
export interface MonteCarloSimulation {
  // ... existing fields ...
  simulation_id: string;
  event_id: string;
  status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'CACHED' | 'PRICE_MOVED' | 'INVALIDATED' | 'FAILED';
  message?: string;
  
  // CANONICAL MARKET VIEWS (REQUIRED)
  market_views?: {
    spread?: MarketView;
    moneyline?: MarketView;
    total?: MarketView;
  };
  
  // ... all other existing fields ...
  [key: string]: any;
}
