import { client } from '../axiosClient';
import type { LoginRequest, LoginResult } from '@/types/api';

/** FR-01 — sign in. Returns a discriminated result covering every auth state. */
export const login = (body: LoginRequest): Promise<LoginResult> =>
  client.post('/auth/login', body).then((r) => r.data);

export const logout = (): Promise<{ ok: boolean }> =>
  client.post('/auth/logout').then((r) => r.data);
