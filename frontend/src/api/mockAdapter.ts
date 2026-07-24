import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { ApiError, resolveRequest } from '@/mocks/handlers';

/**
 * Mock adapter (§9.3). Resolves requests against the in-memory handlers after an
 * artificial latency jittered ±40% around VITE_MOCK_LATENCY_MS. Prediction runs
 * get a longer, variable delay (900–2400ms) so skeletons and the run-time readout
 * are real. This file is the ONLY thing bypassed when mocks are turned off.
 */
const BASE_LATENCY = Number(import.meta.env.VITE_MOCK_LATENCY_MS ?? 420);

function jitter(base: number): number {
  return Math.round(base * (0.6 + Math.random() * 0.8)); // ±40%
}

function delayFor(config: InternalAxiosRequestConfig): number {
  const url = config.url ?? '';
  if (/\/predict$/.test(url)) return 900 + Math.round(Math.random() * 1500); // 900–2400ms
  return jitter(BASE_LATENCY);
}

export const mockAdapter: AxiosAdapter = (config) =>
  new Promise<AxiosResponse>((resolve, reject) => {
    const ms = delayFor(config);
    setTimeout(() => {
      try {
        const data = resolveRequest(config);
        resolve({
          data,
          status: 200,
          statusText: 'OK',
          headers: {},
          config,
        });
      } catch (err) {
        if (err instanceof ApiError) {
          reject({
            isAxiosError: true,
            message: err.message,
            config,
            response: {
              data: err.body ?? { message: err.message },
              status: err.status,
              statusText: err.message,
              headers: {},
              config,
            },
          });
        } else {
          reject(err);
        }
      }
    }, ms);
  });
