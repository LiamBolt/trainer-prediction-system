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

export const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach the bearer token from authStore on every request.
client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401, clear auth and bounce to the sign-in screen with an expiry flag.
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
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
