
import type { Event, Prediction, AffiliateStat, Referral, ChatMessage, TopAnalyst, User, Bet, AuthResponse, UserCredentials, UserRegistration } from '../types';

const API_BASE_URL = 'http://localhost:8000';

// --- Token Management ---
export const getToken = (): string | null => {
    return localStorage.getItem('authToken');
};

export const setToken = (token: string): void => {
    localStorage.setItem('authToken', token);
};

export const removeToken = (): void => {
    localStorage.removeItem('authToken');
};


// --- Authentication ---
export const registerUser = async (userData: UserRegistration): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Registration failed');
    }
    return response.json();
};

export const loginUser = async (credentials: UserCredentials): Promise<AuthResponse> => {
    const params = new URLSearchParams();
    params.append('username', credentials.email);
    params.append('password', credentials.password);
    
    const response = await fetch(`${API_BASE_URL}/api/token`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: params,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
    }
    
    const data: AuthResponse = await response.json();
    setToken(data.access_token);
    return data;
};


// --- Odds Data ---
export const fetchEvents = async (): Promise<Event[]> => {
    const token = getToken();
    if (!token) {
        throw new Error('No authentication token found.');
    }

    const response = await fetch(`${API_BASE_URL}/api/odds/`, {
        headers: {
            'Authorization': `Bearer ${token}`,
        },
    });

    if (response.status === 401) {
       removeToken();
       throw new Error('Session expired. Please log in again.');
    }

    if (!response.ok) {
        throw new Error('Failed to fetch live event data.');
    }

    return response.json();
};


// --- MOCK DATA FOR OTHER FEATURES (to be replaced) ---
const MOCK_PREDICTIONS: Prediction[] = [
  { event_id: 'evt001', confidence: 0.85 },
  { event_id: 'evt002', confidence: 0.68 },
  { event_id: 'evt003', confidence: 0.48 },
];

const MOCK_AFFILIATE_STATS: AffiliateStat[] = [
    { label: 'Total Referrals', value: '128', change: '+12 this month', changeType: 'increase' },
    { label: 'Active Subscriptions', value: '82', change: '+5 this month', changeType: 'increase' },
    { label: 'Commission Rate', value: '25%', change: 'Tier 2', changeType: 'increase' },
    { label: 'Monthly Earnings', value: '$1,230.00', change: '-$50 vs last month', changeType: 'decrease' },
]

const MOCK_REFERRALS: Referral[] = [
    { id: 'ref01', user: 'user_fanatic_22', date_joined: '2024-07-21', status: 'Active', commission: 15.00 },
    { id: 'ref02', user: 'bet_believer', date_joined: '2024-07-19', status: 'Active', commission: 15.00 },
    { id: 'ref03', user: 'sports_guru99', date_joined: '2024-07-15', status: 'Cancelled', commission: 0.00 },
];

const MOCK_CHAT_MESSAGES: ChatMessage[] = [
    { id: 'msg01', user: { username: 'BetMasterFlex', avatarUrl: 'https://i.pravatar.cc/150?u=BetMasterFlex' }, message: 'That Lakers prediction is bold. I\'m taking the points with the Celtics.', timestamp: '2 min ago' },
    { id: 'msg02', user: { username: 'StatsGeek', avatarUrl: 'https://i.pravatar.cc/150?u=StatsGeek' }, message: 'The AI has been hot on overs lately. Tailing the 225.5 total.', timestamp: '1 min ago' },
    { id: 'msg03', user: { username: 'Admin', avatarUrl: 'https://i.pravatar.cc/150?u=Admin', is_admin: true }, message: 'Welcome to the community! Remember to bet responsibly.', timestamp: 'Announcement', announcement: true },
];

const MOCK_TOP_ANALYSTS: TopAnalyst[] = [
    { id: 'usr01', rank: 1, username: 'BetMasterFlex', avatarUrl: 'https://i.pravatar.cc/150?u=BetMasterFlex', units: 15.2 },
    { id: 'usr02', rank: 2, username: 'StatsGeek', avatarUrl: 'https://i.pravatar.cc/150?u=StatsGeek', units: 12.8 },
    { id: 'usr03', rank: 3, username: 'ParlayPrincess', avatarUrl: 'https://i.pravatar.cc/150?u=ParlayPrincess', units: 9.5 },
];

const MOCK_LEADERBOARD_USERS: User[] = [
    { id: 'usr01', rank: 1, username: 'BetMasterFlex', avatarUrl: 'https://i.pravatar.cc/150?u=BetMasterFlex', score: 15200, streaks: 8 },
    { id: 'usr02', rank: 2, username: 'StatsGeek', avatarUrl: 'https://i.pravatar.cc/150?u=StatsGeek', score: 12800, streaks: 5 },
    { id: 'usr03', rank: 3, username: 'ParlayPrincess', avatarUrl: 'https://i.pravatar.cc/150?u=ParlayPrincess', score: 9500, streaks: 3 },
    { id: 'usr04', rank: 4, username: 'WagerWizard', avatarUrl: 'https://i.pravatar.cc/150?u=WagerWizard', score: 8700, streaks: 2 },
    { id: 'usr05', rank: 5, username: 'LuckyLocks', avatarUrl: 'https://i.pravatar.cc/150?u=LuckyLocks', score: 8100, streaks: 1 },
];

const simulateApiCall = <T,>(data: T): Promise<T> =>
  new Promise((resolve) => setTimeout(() => resolve(data), 500));

export const getPredictions = (): Promise<Prediction[]> => simulateApiCall(MOCK_PREDICTIONS);
export const getLeaderboard = (): Promise<User[]> => simulateApiCall(MOCK_LEADERBOARD_USERS);
export const getAffiliateStats = (): Promise<AffiliateStat[]> => simulateApiCall(MOCK_AFFILIATE_STATS);
export const getRecentReferrals = (): Promise<Referral[]> => simulateApiCall(MOCK_REFERRALS);
export const getChatMessages = (): Promise<ChatMessage[]> => simulateApiCall(MOCK_CHAT_MESSAGES);
export const getTopAnalysts = (): Promise<TopAnalyst[]> => simulateApiCall(MOCK_TOP_ANALYSTS);
