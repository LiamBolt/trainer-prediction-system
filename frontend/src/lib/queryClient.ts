import { QueryClient } from '@tanstack/react-query';

/**
 * TanStack Query client (§9.2, §14.2). Reference data (specialisations, stations,
 * roles) is stale after 60s; prediction runs use staleTime 0 at the call site.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
