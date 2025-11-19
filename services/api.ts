
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

    const data = await response.json();
    // Backend may return either an array or an object { count, events }
    if (Array.isArray(data)) {
        return normalizeEvents(data);
    }
    if (data && Array.isArray((data as any).events)) {
        return normalizeEvents((data as any).events);
    }
    // Unexpected shape
    throw new Error('Invalid response shape from events API');
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
