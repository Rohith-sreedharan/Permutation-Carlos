// FIX: Added 'leaderboard' and 'profile' to support more pages
export type Page = 'dashboard' | 'community' | 'affiliates' | 'leaderboard' | 'profile' | 'wallet' | 'settings';

export interface Bet {
  type: 'Moneyline' | 'Spread' | 'Total';
  pick: string;
  value: string;
}

export interface Event {
  id: string;
  sport_key: string;
  commence_time: string;
  home_team: string;
  away_team: string;
  bets: Bet[];
  top_prop_bet: string;
}

export interface Prediction {
  event_id: string;
  confidence: number;
}

export interface EventWithPrediction extends Event {
    prediction?: Prediction;
}

// FIX: Added missing User interface for the Leaderboard component
export interface User {
    id: string;
    rank: number;
    username: string;
    avatarUrl: string;
    score: number;
    streaks: number;
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
