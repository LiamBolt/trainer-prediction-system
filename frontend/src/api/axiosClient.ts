import axios, { type AxiosError } from 'axios';
import { useAuthStore } from '@/stores/authStore';
import { mockAdapter } from './mockAdapter';

/**
 * The single Axios instance (§9.3). A request interceptor attaches the bearer
 * token; a response interceptor clears auth and redirects on 401. When
 * VITE_USE_MOCKS === 'true' the instance's adapter is swapped for the mock
 * adapter — turning mocks off is a single .env change with NO code edits.
 */
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';

/**
 * Normalise the API base URL so it ALWAYS targets the versioned API, regardless of
 * how the deployment set VITE_API_URL. Endpoints are written as `/auth/login`,
 * `/trainers`, … so the base must end in `/api/v1` (the backend serves the API there).
 * This accepts any of:
 *   https://host                 → https://host/api/v1
 *   https://host/api             → https://host/api/v1
 *   https://host/api/v1          → https://host/api/v1   (unchanged)
 * and trims trailing slashes, so a missing or partial prefix can no longer 404 login.
 */
function resolveApiBaseUrl(): string {
  const raw = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '');
  if (raw.endsWith('/api/v1')) return raw;
  if (raw.endsWith('/api')) return `${raw}/v1`;
  return `${raw}/api/v1`;
}

export const client = axios.create({
  baseURL: resolveApiBaseUrl(),
  headers: { 'Content-Type': 'application/json' },
});

// Attach the bearer token from authStore on every request.
client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401, clear auth and bounce to the sign-in screen with an expiry flag — but ONLY
// for a mid-session token expiry, never for the auth endpoints themselves. A 401 from
// /auth/login is "wrong password" and must reach the sign-in form as INVALID; a 401
// from /auth/refresh is a dead session the form handles directly. Treating those as an
// expiry redirect would replace "Incorrect username or password" with a full-page
// bounce to "Your session ended".
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const url = error.config?.url ?? '';
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh');
    if (error.response?.status === 401 && !isAuthEndpoint) {
      useAuthStore.getState().clear();
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/signin')) {
        window.location.assign('/signin?expired=1');
      }
    }
    return Promise.reject(error);
  },
);

// The ONLY line that differs between mock and live modes.
if (USE_MOCKS) {
  client.defaults.adapter = mockAdapter;
}
