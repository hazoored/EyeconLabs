/**
 * API utility for making requests to the backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

interface ApiOptions {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
    body?: Record<string, unknown>;
    token?: string;
}

interface ApiResponse<T> {
    data?: T;
    error?: string;
    ok: boolean;
}

export async function api<T>(endpoint: string, options: ApiOptions = {}): Promise<ApiResponse<T>> {
    const { method = 'GET', body, token } = options;

    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method,
            headers,
            body: body ? JSON.stringify(body) : undefined,
        });

        const data = await response.json();

        if (!response.ok) {
            return {
                error: data.detail || 'An error occurred',
                ok: false,
            };
        }

        return {
            data,
            ok: true,
        };
    } catch (error) {
        return {
            error: error instanceof Error ? error.message : 'Network error',
            ok: false,
        };
    }
}

// Auth helpers
export function setToken(token: string, type: 'admin' | 'client') {
    if (typeof window !== 'undefined') {
        const key = `eyeconbumps_${type}_token`;
        console.log(`[API] Setting ${type} token to ${key}`);
        localStorage.setItem(key, token);
    }
}

export function getToken(type: 'admin' | 'client'): string | null {
    if (typeof window !== 'undefined') {
        const key = `eyeconbumps_${type}_token`;
        return localStorage.getItem(key);
    }
    return null;
}

export function clearToken(type: 'admin' | 'client') {
    if (typeof window !== 'undefined') {
        const key = `eyeconbumps_${type}_token`;
        console.log(`[API] Clearing ${type} token: ${key}`);
        localStorage.removeItem(key);
        // Also clear legacy keys
        localStorage.removeItem(type === 'admin' ? 'admin_token' : 'eyecon_token');
    }
}

export function isLoggedIn(type: 'admin' | 'client'): boolean {
    return !!getToken(type);
}
