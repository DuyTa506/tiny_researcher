import api from './api';
import type { AuthUser, TokenResponse } from '@/lib/types';

const TOKEN_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';

export const authService = {
    // ── Token management ──

    getToken: (): string | null => {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem(TOKEN_KEY);
    },

    getRefreshToken: (): string | null => {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem(REFRESH_KEY);
    },

    setTokens: (tokens: TokenResponse) => {
        localStorage.setItem(TOKEN_KEY, tokens.access_token);
        localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    },

    clearTokens: () => {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
    },

    // ── API calls ──

    register: (data: { email: string; username: string; password: string; full_name?: string }) =>
        api.post<AuthUser>('/auth/register', data),

    login: (email: string, password: string) =>
        api.post<TokenResponse>('/auth/login', { email, password }),

    refresh: (refreshToken: string) =>
        api.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken }),

    getProfile: () =>
        api.get<AuthUser>('/auth/me'),

    updateProfile: (data: { full_name?: string; username?: string; preferences?: Record<string, unknown> }) =>
        api.put<AuthUser>('/auth/me', data),

    changePassword: (currentPassword: string, newPassword: string) =>
        api.post('/auth/me/change-password', {
            current_password: currentPassword,
            new_password: newPassword,
        }),

    // ── Email verification ──

    verifyEmail: (token: string) =>
        api.post('/auth/verify-email', null, { params: { token } }),

    resendVerification: () =>
        api.post('/auth/resend-verification'),

    // ── Password reset ──

    requestPasswordReset: (email: string) =>
        api.post('/auth/password-reset', { email }),

    confirmPasswordReset: (token: string, newPassword: string) =>
        api.post('/auth/password-reset/confirm', { token, new_password: newPassword }),

    // ── Google OAuth ──

    googleAuth: (code: string) =>
        api.post<TokenResponse>('/auth/google', { code }),
};
