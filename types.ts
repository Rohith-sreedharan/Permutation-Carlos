// FIX: Added 'leaderboard', 'profile', 'billing', 'earnings' to support more pages
export type Page = 'dashboard' | 'community' | 'trust-loop' | 'architect' | 'affiliates' | 'leaderboard' | 'profile' | 'wallet' | 'billing' | 'earnings' | 'settings' | 'gameDetail' | 'onboarding';

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

// FIX: Updated User interface with new tier system (STARTER, EXPLORER, PRO, ELITE)
export interface User {
    id: string;
    rank: number;
    username: string;
    avatarUrl: string;
    score: number;
    streaks: number;
    tier?: 'STARTER' | 'EXPLORER' | 'PRO' | 'ELITE' | 'FOUNDER';
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
  volatility_index: number | string;
  volatility_score?: number;
  volatility?: string;
  confidence_score: number;
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
  }>;
  confidence_intervals?: {
    ci_68: [number, number];
    ci_95: [number, number];
    ci_99: [number, number];
  };
  created_at: string;
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

// Beat Vegas - Subscription Tier Types
export interface SubscriptionTier {
  id: 'starter' | 'pro' | 'sharps_room' | 'founder';
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
