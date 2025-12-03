
import type { Event, Prediction, AffiliateStat, Referral, ChatMessage, TopAnalyst, User, Bet, AuthResponse, UserCredentials, UserRegistration, MonteCarloSimulation, CLVDataPoint, CLVStats, PerformanceMetrics } from '../types';

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

// --- Generic API Request ---
export const apiRequest = async <T = any>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> => {
    const token = getToken();
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
    }

    return response.json();
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

/**
 * Verify if the current token is valid and user exists
 * Returns user data if valid, throws error if invalid
 */
export const verifyToken = async (): Promise<User> => {
    const token = getToken();
    if (!token) {
        throw new Error('No token found');
    }
    
    try {
        // Try to fetch current user data - this validates token and user existence
        const response = await fetch(`${API_BASE_URL}/api/users/me`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });
        
        if (!response.ok) {
            // Token is invalid or user doesn't exist
            removeToken();
            throw new Error('Invalid or expired token');
        }
        
        return response.json();
    } catch (error) {
        removeToken();
        throw error;
    }
};


// --- Odds Data ---
// Fetches today's NBA events by default (EST), can be extended for other sports/dates
// Fetch events from database (uses stored events with EST filtering)
export const fetchEventsFromDB = async (
    sportKey?: string,
    date?: string,
    upcomingOnly: boolean = true,
    limit: number = 100
): Promise<Event[]> => {
    // Default to today's EST date if not provided
    let targetDate = date;
    if (!targetDate) {
        const now = new Date();
        // Get EST date string directly using Intl.DateTimeFormat
        const formatter = new Intl.DateTimeFormat('en-CA', { 
            timeZone: 'America/New_York',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
        targetDate = formatter.format(now); // Returns "YYYY-MM-DD" format
    }
    
    let url = `${API_BASE_URL}/api/odds/list?date=${encodeURIComponent(targetDate)}&upcoming_only=${upcomingOnly}&limit=${limit}`;
    if (sportKey) {
        url += `&sport=${encodeURIComponent(sportKey)}`;
    }
    
    console.log('[fetchEventsFromDB] Calling:', url);
    const res = await fetch(url);
    console.log('[fetchEventsFromDB] Response status:', res.status);
    console.log('[fetchEventsFromDB] Response status:', res.status);
    if (!res.ok) throw new Error(`Failed to fetch events: ${res.status}`);
    const data = await res.json();
    console.log('[fetchEventsFromDB] Response data:', { 
        isArray: Array.isArray(data), 
        hasEvents: !!data?.events,
        count: data?.count,
        eventsLength: Array.isArray(data) ? data.length : (data?.events?.length ?? 0)
    });
    const evs = Array.isArray(data) ? data : (data?.events ?? []);
    console.log('[fetchEventsFromDB] Returning events:', evs.length);
    return normalizeEvents(evs);
};

export const fetchEvents = async (
    sportKey: string = 'basketball_nba',
    date?: string,
    regions: string = 'us,us2,eu,uk',
    markets: string = 'h2h,spreads,totals',
    dateBasis: string = 'est'
): Promise<Event[]> => {
    // Default to today's EST date if not provided
    let targetDate = date;
    if (!targetDate) {
        const now = new Date();
        // Convert to America/New_York (EST/EDT) date string
        const estNow = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
        targetDate = estNow.toISOString().slice(0, 10);
    }
    const url = `${API_BASE_URL}/api/odds/realtime/by-date?sport=${encodeURIComponent(sportKey)}&date=${encodeURIComponent(targetDate)}&regions=${encodeURIComponent(regions)}&markets=${encodeURIComponent(markets)}&date_basis=${encodeURIComponent(dateBasis)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed realtime fetch: ${res.status}`);
    const data = await res.json();
    const evs = Array.isArray(data) ? data : (data?.events ?? []);
    return normalizeEvents(evs);
};

// Real-time by-date fetch (EST)
export const fetchEventsByDateRealtime = async (
    sportKey: string,
    estDate: string,
    regions: string = 'us,us2,eu,uk',
    markets: string = 'h2h,spreads,totals'
): Promise<Event[]> => {
    const url = `${API_BASE_URL}/api/odds/realtime/by-date?sport=${encodeURIComponent(sportKey)}&date=${encodeURIComponent(estDate)}&regions=${encodeURIComponent(regions)}&markets=${encodeURIComponent(markets)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed realtime fetch: ${res.status}`);
    const data = await res.json();
    const evs = Array.isArray(data) ? data : (data?.events ?? []);
    return normalizeEvents(evs);
};

// Helper to normalize event field names from backend
function normalizeEvents(events: any[]): Event[] {
    return events.map(event => ({
        ...event,
        id: event.id || event.event_id, // Backend uses event_id, frontend expects id
    }));
}


// --- Real backend-powered helpers for other features ---
const ensureAuthHeaders = () => {
    const token = getToken();
    if (!token) throw new Error('No authentication token found.');
    return { 'Authorization': `Bearer ${token}` };
};

export const getPredictions = async (): Promise<Prediction[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/predictions`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch predictions');
    const data = await res.json();
    if (Array.isArray(data)) return data as Prediction[];
    if (data && Array.isArray((data as any).predictions)) return (data as any).predictions;
    return [];
};

export const getLeaderboard = async (): Promise<User[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/leaderboard`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch leaderboard');
    const data = await res.json();
    if (Array.isArray(data)) return data as User[];
    if (data && Array.isArray((data as any).leaderboard)) return (data as any).leaderboard;
    return [];
};

export const getAffiliateStats = async (): Promise<AffiliateStat[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/affiliate-stats`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch affiliate stats');
    const data = await res.json();
    if (Array.isArray(data)) return data as AffiliateStat[];
    if (data && Array.isArray((data as any).affiliate_stats)) return (data as any).affiliate_stats;
    return [];
};

export const getRecentReferrals = async (): Promise<Referral[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/referrals`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch referrals');
    const data = await res.json();
    if (Array.isArray(data)) return data as Referral[];
    if (data && Array.isArray((data as any).referrals)) return (data as any).referrals;
    return [];
};

export const getChatMessages = async (): Promise<ChatMessage[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/chat`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch chat messages');
    const data = await res.json();
    if (Array.isArray(data)) return data as ChatMessage[];
    if (data && Array.isArray((data as any).messages)) return (data as any).messages;
    return [];
};

export const getTopAnalysts = async (): Promise<TopAnalyst[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/top-analysts`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch top analysts');
    const data = await res.json();
    if (Array.isArray(data)) return data as TopAnalyst[];
    if (data && Array.isArray((data as any).analysts)) return (data as any).analysts;
    return [];
};

// --- Account endpoints ---
export const getUserProfile = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/profile`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch profile');
    const data = await res.json();
    return data.profile || data;
};

export const getUserWallet = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/wallet`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch wallet');
    const data = await res.json();
    return data.wallet || data;
};

export const getUserSettings = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/settings`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch settings');
    const data = await res.json();
    return data.settings || data;
};

export const updateUserSettings = async (settings: any) => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/account/settings`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(settings),
    });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to update settings');
    const data = await res.json();
    return data.settings || data;
};

// --- Beat Vegas - Monte Carlo Simulation endpoints ---
export const fetchSimulation = async (eventId: string): Promise<MonteCarloSimulation> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/simulations/${eventId}`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch simulation');
    return res.json();
};

export const requestSimulation = async (eventId: string, iterations: number = 100000): Promise<MonteCarloSimulation> => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/simulations/run`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ event_id: eventId, iterations }),
    });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to request simulation');
    return res.json();
};

// --- Beat Vegas - CLV Tracking endpoints ---
export const fetchCLVData = async (timeRange: '7d' | '30d' | '90d' | 'all' = '30d'): Promise<{ picks: CLVDataPoint[]; stats: CLVStats }> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/performance/clv?range=${timeRange}`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch CLV data');
    return res.json();
};

// --- Beat Vegas - Performance Metrics endpoints ---
export const fetchPerformanceReport = async (timeRange: '7d' | '30d' | '90d' | 'season' = '30d'): Promise<PerformanceMetrics> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/performance/report?range=${timeRange}`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch performance report');
    return res.json();
};

// --- Beat Vegas - Tier Management endpoints ---
export const getUserTier = async (): Promise<{ tier: 'starter' | 'pro' | 'sharps_room' | 'founder'; features: string[] }> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/tier`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch user tier');
    return res.json();
};

export const upgradeTier = async (targetTier: 'pro' | 'sharps_room' | 'founder'): Promise<{ success: boolean; message: string }> => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/account/upgrade`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ tier: targetTier }),
    });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to upgrade tier');
    return res.json();
};

// --- Subscription Management ---
export const getSubscriptionStatus = async (): Promise<{
    tier: string;
    renewalDate: string;
    paymentMethod?: { last4: string; brand: string };
    status: 'active' | 'canceled' | 'past_due';
}> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/subscription/status`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch subscription');
    return res.json();
};

// --- Affiliate Earnings ---
export const getAffiliateEarnings = async (): Promise<{
    lifetimeEarnings: number;
    pendingPayout: number;
    nextPayoutDate: string;
    isConnected: boolean;
    payouts: Array<{ id: string; date: string; amount: number; status: 'completed' | 'pending' | 'failed' }>;
}> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/affiliate/earnings`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch earnings');
    return res.json();
};

// --- Risk Profile ---
export const getRiskProfile = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/user/risk-profile`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch risk profile');
    return res.json();
};

export const updateRiskProfile = async (profile: any) => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/user/risk-profile`, {
        method: 'POST',
        headers,
        body: JSON.stringify(profile),
    });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to update risk profile');
    return res.json();
};

// --- Community Chat ---
export const sendChatMessage = async (message: string, channel: string = 'general') => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/community/messages`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message, channel }),
    });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to send message');
    return res.json();
};

// --- Default Export for Axios-like API ---
const api = {
    get: async <T = any>(url: string, config?: RequestInit): Promise<{ data: T }> => {
        const token = getToken();
        const headers: HeadersInit = {
            ...config?.headers,
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(url, {
            ...config,
            method: 'GET',
            headers,
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        const data = await response.json();
        return { data };
    },
    post: async <T = any>(url: string, body?: any, config?: RequestInit): Promise<{ data: T }> => {
        const token = getToken();
        const headers: HeadersInit = {
            'Content-Type': 'application/json',
            ...config?.headers,
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(url, {
            ...config,
            method: 'POST',
            headers,
            body: body ? JSON.stringify(body) : undefined,
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        const data = await response.json();
        return { data };
    },
};

export default api;

