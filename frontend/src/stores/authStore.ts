import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { RoleName, User } from '@/types/domain';

/**
 * authStore — global client auth state (§9.2). Holds the current user, role, and
 * token. Server data is never copied here beyond the session identity. The token
 * is attached by the axios request interceptor; a 401 clears this store.
 */
interface AuthState {
  user: User | null;
  token: string | null;
  expiresAt: string | null;
  role: RoleName | null;
  setSession: (session: { user: User; token: string; expiresAt: string }) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      expiresAt: null,
      role: null,
      setSession: ({ user, token, expiresAt }) =>
        set({ user, token, expiresAt, role: user.role }),
      clear: () => set({ user: null, token: null, expiresAt: null, role: null }),
    }),
    { name: 'tps-auth' },
  ),
);

export const getAuthToken = (): string | null => useAuthStore.getState().token;
