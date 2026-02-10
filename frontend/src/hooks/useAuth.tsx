'use client';

import {
    createContext,
    useContext,
    useEffect,
    useState,
    useCallback,
    type ReactNode,
} from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { authService } from '@/services/auth';
import type { AuthUser } from '@/lib/types';

interface AuthContextValue {
    user: AuthUser | null;
    isLoading: boolean;
    isAuthenticated: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (data: { email: string; username: string; password: string; full_name?: string }) => Promise<void>;
    logout: () => void;
    refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
    login: async () => { },
    register: async () => { },
    logout: () => { },
    refreshUser: async () => { },
});

export function useAuth() {
    return useContext(AuthContext);
}

const PUBLIC_ROUTES = ['/login', '/register', '/auth/verify', '/auth/reset-password', '/auth/forgot-password'];

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<AuthUser | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const router = useRouter();
    const pathname = usePathname();

    const isPublicRoute = PUBLIC_ROUTES.some((route) => pathname?.startsWith(route));

    // Load user on mount
    useEffect(() => {
        const token = authService.getToken();
        if (!token) {
            setIsLoading(false);
            if (!isPublicRoute) {
                router.replace('/login');
            }
            return;
        }

        authService
            .getProfile()
            .then((res) => {
                setUser(res.data);
            })
            .catch(async () => {
                // Try refresh
                const refreshToken = authService.getRefreshToken();
                if (refreshToken) {
                    try {
                        const res = await authService.refresh(refreshToken);
                        authService.setTokens(res.data);
                        const profile = await authService.getProfile();
                        setUser(profile.data);
                    } catch {
                        authService.clearTokens();
                        if (!isPublicRoute) router.replace('/login');
                    }
                } else {
                    authService.clearTokens();
                    if (!isPublicRoute) router.replace('/login');
                }
            })
            .finally(() => setIsLoading(false));
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const login = useCallback(async (email: string, password: string) => {
        const res = await authService.login(email, password);
        authService.setTokens(res.data);
        const profile = await authService.getProfile();
        setUser(profile.data);
        router.replace('/');
    }, [router]);

    const register = useCallback(async (data: { email: string; username: string; password: string; full_name?: string }) => {
        await authService.register(data);
        // Auto-login after registration
        const res = await authService.login(data.email, data.password);
        authService.setTokens(res.data);
        const profile = await authService.getProfile();
        setUser(profile.data);
        router.replace('/');
    }, [router]);

    const logout = useCallback(() => {
        authService.clearTokens();
        setUser(null);
        router.replace('/login');
    }, [router]);

    const refreshUser = useCallback(async () => {
        try {
            const profile = await authService.getProfile();
            setUser(profile.data);
        } catch {
            // ignore
        }
    }, []);

    return (
        <AuthContext.Provider
            value={{
                user,
                isLoading,
                isAuthenticated: !!user,
                login,
                register,
                logout,
                refreshUser,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}
