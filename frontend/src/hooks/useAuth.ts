import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { authApi } from '@/api/endpoints';
import type { LoginResult } from '@/types/api';
import type { RoleName } from '@/types/domain';

/** Demo accounts for the mocks-only role switcher (§8.9). */
export const DEMO_ACCOUNTS: Record<RoleName, string> = {
  TRAINING_ADMINISTRATOR: 'admin.training',
  TRAINING_OFFICER: 'officer.training',
  TRAINER: 'trainer',
  SYSTEM_ADMINISTRATOR: 'sysadmin',
};

// Must match the backend seed's demo password (app/core/constants.py: DEMO_PASSWORD).
// Used only by the mocks-only demo-account filler and role switcher (§8.9).
export const DEMO_PASSWORD = 'Tps@2026#Demo';

export function useAuth() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const role = useAuthStore((s) => s.role);
  const setSession = useAuthStore((s) => s.setSession);
  const clear = useAuthStore((s) => s.clear);

  const signIn = useCallback(
    async (username: string, password: string): Promise<LoginResult> => {
      const result = await authApi.login({ username, password });
      if (result.outcome === 'SUCCESS') setSession(result.session);
      return result;
    },
    [setSession],
  );

  const signOut = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clear();
      navigate('/signin');
    }
  }, [clear, navigate]);

  /** Mocks-only: jump to another role's demo account without signing out (§8.9). */
  const switchRole = useCallback(
    async (target: RoleName) => {
      const result = await authApi.login({ username: DEMO_ACCOUNTS[target], password: DEMO_PASSWORD });
      if (result.outcome === 'SUCCESS') {
        setSession(result.session);
        navigate('/dashboard');
      }
    },
    [setSession, navigate],
  );

  return { user, role, signIn, signOut, switchRole, isAuthenticated: Boolean(user) };
}
