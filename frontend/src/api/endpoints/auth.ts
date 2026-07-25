import axios from 'axios';
import { client } from '../axiosClient';
import type { AuthSession, LoginRequest, LoginResult } from '@/types/api';

/** The extra members the backend adds to a login problem+json body (§6.1). */
interface LoginProblem {
  attemptsRemaining?: number;
  retryAfterSeconds?: number;
  unlockAt?: string;
}

/**
 * FR-01 — sign in.
 *
 * The UI is built around a discriminated {@link LoginResult}, but the real backend
 * does not send that envelope: it returns the bare {@link AuthSession} on 200 and
 * signals every other outcome with an HTTP status —
 *   401 → invalid credentials (body carries `attemptsRemaining`),
 *   423 → account locked      (body carries `retryAfterSeconds` + `unlockAt`),
 *   403 → account deactivated.
 * (The mock adapter fabricated the envelope, which is why sign-in worked against mocks
 * but not the live API.) This function is where the two shapes meet. Only genuinely
 * unexpected failures — 429 rate-limit, network errors, 5xx — propagate to the caller.
 */
export const login = async (body: LoginRequest): Promise<LoginResult> => {
  try {
    const { data } = await client.post<AuthSession>('/auth/login', body);
    return { outcome: 'SUCCESS', session: data };
  } catch (err) {
    if (axios.isAxiosError(err) && err.response) {
      const { status } = err.response;
      const problem = (err.response.data ?? {}) as LoginProblem;

      if (status === 401) {
        return { outcome: 'INVALID', attemptsRemaining: problem.attemptsRemaining ?? 0 };
      }
      if (status === 423) {
        const unlockAt =
          problem.unlockAt ??
          new Date(Date.now() + (problem.retryAfterSeconds ?? 900) * 1000).toISOString();
        return { outcome: 'LOCKED', unlockAt };
      }
      if (status === 403) {
        return { outcome: 'DEACTIVATED' };
      }
    }
    // 429 / network / 5xx — the sign-in form surfaces these as a generic message.
    throw err;
  }
};

export const logout = (): Promise<{ ok: boolean }> =>
  client.post('/auth/logout').then((r) => r.data);
