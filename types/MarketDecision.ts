/**
 * CANONICAL MARKET DECISION CONTRACT
 * 
 * This is the ONLY object the UI is allowed to consume.
 * UI MUST NOT compute any of these fields.
 * Backend computes everything. UI renders verbatim.
 * 
 * Per spec: "If a function computes market logic and does NOT return a full MarketDecision, it must not exist."
 */

export type MarketType = 'spread' | 'moneyline' | 'total';

export type Classification = 
  | 'EDGE'              // Official trade candidate
  | 'LEAN'              // Info-only / low confidence
  | 'MARKET_ALIGNED'    // No edge
  | 'NO_ACTION';        // Blocked by risk/integrity

export type ReleaseStatus = 
  | 'OFFICIAL'                // Eligible for release + telegram
  | 'INFO_ONLY'               // Visible but not a pick
  | 'BLOCKED_BY_RISK'         // Blocked by risk flags
  | 'BLOCKED_BY_INTEGRITY';   // Blocked by integrity violations

export interface MarketDecision {
  // Identity
  league: string;              // e.g., "NBA", "NFL", "NCAAF"
  game_id: string;             // Internal event ID
  odds_event_id: string;       // Provider event ID (prevents cross-game bleed)
  market_type: MarketType;
  
  // CANONICAL IDENTIFIERS (required for audit + display)
  decision_id: string;         // UUID for this specific decision
  selection_id: string;        // Canonical selection ID
  preferred_selection_id: string; // The bettable leg anchor
  market_selections: Array<{   // Both sides of the market
    selection_id: string;
    team_id?: string;
    team_name?: string;
    side?: 'OVER' | 'UNDER' | 'HOME' | 'AWAY';
    line?: number;
    odds?: number;
  }>;
  
  // Pick (what the model recommends)
  pick: {
    // For spread/moneyline
    team_id?: string;          // Canonical team ID
    team_name?: string;        // Display name
    side?: 'HOME' | 'AWAY';    // Optional home/away flag
    
    // For totals
    total_side?: 'OVER' | 'UNDER';
  };
  
  // Market data (from sportsbook)
  market: {
    line?: number;             // Spread (signed for pick team) or Total points
    odds?: number;             // American odds (if available)
  };
  
  // Model data (from simulation)
  model: {
    fair_line?: number;        // Spread: signed for same pick team
    fair_total?: number;       // Total: model projected total
    win_prob?: number;         // Moneyline: win probability
  };
  
  // Fair selection (fair line for preferred selection)
  fair_selection: {
    line?: number;             // Spread: fair line for preferred team
    total?: number;            // Total: fair total for preferred side
    team_id?: string;          // Team anchor for spread
    side?: 'OVER' | 'UNDER';   // Side anchor for total
  };
  
  // Probabilities (bound to pick)
  probabilities: {
    model_prob: number;        // Model probability of cover/win/over
    market_implied_prob: number; // Market-implied probability (vig-aware)
  };
  
  // Edge metrics
  edge: {
    edge_points?: number;      // Spread/Total edge in points
    edge_ev?: number;          // Moneyline edge in EV
    edge_grade?: string;       // S/A/B/C grade (optional)
  };
  
  // Classification (backend-computed)
  classification: Classification;
  release_status: ReleaseStatus;
  
  // Reasons (pre-written by backend)
  reasons: string[];           // Powers "Why This Edge Exists"
  
  // Risk factors
  risk?: {
    volatility_flag?: string;
    injury_impact?: number;
    clv_forecast?: number;
    blocked_reason?: string;
  };
  
  // Debug metadata
  debug: {
    inputs_hash: string;       // Hash of odds snapshot + sim run + config (MUST match across all markets)
    odds_timestamp?: string;
    sim_run_id?: string;
    trace_id: string;          // Trace ID for audit/debugging (MUST match across all markets)
    config_profile?: string;   // balanced/high-vol/high-confidence
    decision_version: number;  // Monotonic version (MUST be identical across all markets in same response)
    computed_at: string;       // ISO timestamp (MUST match across all markets)
  };
  
  // Integrity violations (if blocked)
  validator_failures?: string[];
}

/**
 * Response from unified /decisions endpoint
 */
export interface GameDecisions {
  spread: MarketDecision | null;
  moneyline: MarketDecision | null;
  total: MarketDecision | null;
  meta: {
    inputs_hash: string;
    computed_at: string;
    league: string;
    game_id: string;
  };
}
