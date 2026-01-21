
import type { Event, Prediction, AffiliateStat, Referral, ChatMessage, TopAnalyst, User, Bet, AuthResponse, UserCredentials, UserRegistration, MonteCarloSimulation, CLVDataPoint, CLVStats, PerformanceMetrics } from '../types';

// Use environment variable or fall back to localhost for development
export const API_BASE_URL = import.meta.env.VITE_API_URL || (
  window.location.hostname === 'localhost' 
    ? 'http://localhost:8000' 
    : `${window.location.protocol}//${window.location.host}`
);

// --- Safe JSON Parser ---
/**
 * Safely parse JSON response, handling HTML error pages
 */
const safeJsonParse = async (response: Response): Promise<any> => {
    const text = await response.text();
    
    // Check if response is HTML (common when server returns error page)
    if (text.trim().startsWith('<')) {
        console.error('❌ Server returned HTML instead of JSON:', text.substring(0, 200));
        throw new Error(`Server error: Received HTML instead of JSON (status ${response.status})`);
    }
    
    try {
        return JSON.parse(text);
    } catch (err) {
        console.error('❌ JSON parse error:', err, 'Response:', text.substring(0, 200));
        throw new Error(`Invalid JSON response from server`);
    }
};

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
        const errorData = await safeJsonParse(response).catch(() => ({ detail: 'Request failed' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
    }

    return safeJsonParse(response);
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
        const errorData = await safeJsonParse(response);
        throw new Error(errorData.detail || 'Registration failed');
    }
    return safeJsonParse(response);
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
        const errorData = await safeJsonParse(response);
        throw new Error(errorData.detail || 'Login failed');
    }
    
    const data = await safeJsonParse(response);
    
    // Check if 2FA is required
    if (data.requires_2fa) {
        return data; // Return the temp_token for 2FA verification
    }
    
    // Normal login without 2FA
    setToken(data.access_token);
    return data;
};

export const verify2FALogin = async (tempToken: string, code: string): Promise<AuthResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/verify-2fa?temp_token=${encodeURIComponent(tempToken)}&code=${encodeURIComponent(code)}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
    });

    if (!response.ok) {
        const errorData = await safeJsonParse(response);
        throw new Error(errorData.detail || 'Invalid verification code');
    }
    
    const data: AuthResponse = await safeJsonParse(response);
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
        
        return safeJsonParse(response);
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
    const data = await safeJsonParse(res);
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
    const data = await safeJsonParse(res);
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
    const data = await safeJsonParse(res);
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
    const data = await safeJsonParse(res);
    if (Array.isArray(data)) return data as Prediction[];
    if (data && Array.isArray((data as any).predictions)) return (data as any).predictions;
    return [];
};

export const getLeaderboard = async (): Promise<User[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/leaderboard`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch leaderboard');
    const data = await safeJsonParse(res);
    if (Array.isArray(data)) return data as User[];
    if (data && Array.isArray((data as any).leaderboard)) return (data as any).leaderboard;
    return [];
};

export const getAffiliateStats = async (): Promise<AffiliateStat[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/affiliate-stats`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch affiliate stats');
    const data = await safeJsonParse(res);
    if (Array.isArray(data)) return data as AffiliateStat[];
    if (data && Array.isArray((data as any).affiliate_stats)) return (data as any).affiliate_stats;
    return [];
};

export const getRecentReferrals = async (): Promise<Referral[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/referrals`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch referrals');
    const data = await safeJsonParse(res);
    if (Array.isArray(data)) return data as Referral[];
    if (data && Array.isArray((data as any).referrals)) return (data as any).referrals;
    return [];
};

export const getChatMessages = async (): Promise<ChatMessage[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/chat`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch chat messages');
    const data = await safeJsonParse(res);
    if (Array.isArray(data)) return data as ChatMessage[];
    if (data && Array.isArray((data as any).messages)) return (data as any).messages;
    return [];
};

export const getTopAnalysts = async (): Promise<TopAnalyst[]> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/core/top-analysts`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch top analysts');
    const data = await safeJsonParse(res);
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
    const data = await safeJsonParse(res);
    return data.profile || data;
};

export const getUserWallet = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/wallet`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch wallet');
    const data = await safeJsonParse(res);
    return data.wallet || data;
};

export const getUserSettings = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/settings`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch settings');
    const data = await safeJsonParse(res);
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
    const data = await safeJsonParse(res);
    return data.settings || data;
};

// --- Account Management ---
export const changePassword = async (currentPassword: string, newPassword: string) => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/account/change-password`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (res.status === 401) { 
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Authentication failed'); 
    }
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Failed to change password');
    }
    return safeJsonParse(res);
};

export const enable2FA = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/2fa/enable`, {
        method: 'POST',
        headers,
    });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Failed to enable 2FA');
    }
    return safeJsonParse(res);
};

export const verify2FA = async (code: string) => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/account/2fa/verify`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ code }),
    });
    if (res.status === 401) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Invalid verification code');
    }
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Failed to verify 2FA');
    }
    return safeJsonParse(res);
};

export const disable2FA = async (password: string) => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/account/2fa/disable`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ password }),
    });
    if (res.status === 401) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Incorrect password');
    }
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Failed to disable 2FA');
    }
    return safeJsonParse(res);
};

export const get2FAStatus = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/2fa/status`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to get 2FA status');
    return safeJsonParse(res);
};

export const deleteAccount = async (password: string, confirmation: string) => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/account/delete`, {
        method: 'DELETE',
        headers,
        body: JSON.stringify({ password, confirmation }),
    });
    if (res.status === 401) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Incorrect password');
    }
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Failed to delete account');
    }
    return safeJsonParse(res);
};

// --- Passkey / Biometric Authentication ---
export const beginPasskeyRegistration = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/passkey/register-begin`, {
        method: 'POST',
        headers,
    });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Failed to start passkey registration');
    }
    return safeJsonParse(res);
};

export const completePasskeyRegistration = async (credential: any) => {
    const headers = { ...ensureAuthHeaders(), 'Content-Type': 'application/json' };
    const res = await fetch(`${API_BASE_URL}/api/account/passkey/register-complete`, {
        method: 'POST',
        headers,
        body: JSON.stringify(credential),
    });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Failed to complete passkey registration');
    }
    return safeJsonParse(res);
};

export const listPasskeys = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/passkey/list`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch passkeys');
    return safeJsonParse(res);
};

export const deletePasskey = async (credentialId: string) => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/passkey/${credentialId}`, {
        method: 'DELETE',
        headers,
    });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Failed to delete passkey');
    }
    return safeJsonParse(res);
};

export const beginPasskeyLogin = async (email: string) => {
    const res = await fetch(`${API_BASE_URL}/api/passkey/login-begin?email=${encodeURIComponent(email)}`, {
        method: 'POST',
    });
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Failed to start passkey login');
    }
    return safeJsonParse(res);
};

export const completePasskeyLogin = async (email: string, credential: any) => {
    const res = await fetch(`${API_BASE_URL}/api/passkey/login-complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, credential }),
    });
    if (!res.ok) {
        const error = await safeJsonParse(res);
        throw new Error(error.detail || 'Passkey authentication failed');
    }
    const data = await safeJsonParse(res);
    setToken(data.access_token);
    return data;
};

// --- Beat Vegas - Monte Carlo Simulation endpoints ---
export const fetchSimulation = async (eventId: string): Promise<MonteCarloSimulation> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/simulations/${eventId}`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (res.status === 422) {
        // Handle structural market errors (staleness is now graceful)
        const error = await safeJsonParse(res);
        if (error.detail?.error === 'STRUCTURAL_MARKET_ERROR') {
            throw new Error(error.detail.message || 'Market data has structural errors');
        }
        throw new Error(error.detail?.message || 'Cannot generate simulation');
    }
    if (!res.ok) throw new Error('Failed to fetch simulation');
    
    const data = await safeJsonParse(res);
    
    // Check integrity_status for graceful degradation warnings
    if (data.integrity_status) {
        const status = data.integrity_status.status;
        if (status === 'stale_line') {
            // Log warning but don't block - simulation is still usable
            console.warn(`⚠️ Simulation uses stale odds (${data.integrity_status.odds_age_hours?.toFixed(1)}h old). Last updated: ${data.integrity_status.last_updated_at}`);
            
            // Optionally add a visual indicator to the data
            data._stale_warning = true;
            data._stale_reason = data.integrity_status.staleness_reason;
            data._odds_age_hours = data.integrity_status.odds_age_hours;
        }
    }
    
    return data;
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
    return safeJsonParse(res);
};

// --- Beat Vegas - CLV Tracking endpoints ---
export const fetchCLVData = async (timeRange: '7d' | '30d' | '90d' | 'all' = '30d'): Promise<{ picks: CLVDataPoint[]; stats: CLVStats }> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/performance/clv?range=${timeRange}`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch CLV data');
    return safeJsonParse(res);
};

// --- Beat Vegas - Performance Metrics endpoints ---
export const fetchPerformanceReport = async (timeRange: '7d' | '30d' | '90d' | 'season' = '30d'): Promise<PerformanceMetrics> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/performance/report?range=${timeRange}`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch performance report');
    return safeJsonParse(res);
};

// --- Beat Vegas - Tier Management endpoints ---
export const getUserTier = async (): Promise<{ tier: 'starter' | 'pro' | 'sharps_room' | 'founder'; features: string[] }> => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/account/tier`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch user tier');
    return safeJsonParse(res);
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
    return safeJsonParse(res);
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
    return safeJsonParse(res);
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
    return safeJsonParse(res);
};

// --- Risk Profile ---
export const getRiskProfile = async () => {
    const headers = ensureAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/api/user/risk-profile`, { headers });
    if (res.status === 401) { removeToken(); throw new Error('Session expired. Please log in again.'); }
    if (!res.ok) throw new Error('Failed to fetch risk profile');
    return safeJsonParse(res);
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
    return safeJsonParse(res);
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
    return safeJsonParse(res);
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
            const errorData = await safeJsonParse(response).catch(() => ({ detail: 'Request failed' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        const data = await safeJsonParse(response);
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
            const errorData = await safeJsonParse(response).catch(() => ({ detail: 'Request failed' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        const data = await safeJsonParse(response);
        return { data };
    },
};

export default api;

