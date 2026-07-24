import { useEffect } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { RouterProvider } from 'react-router-dom';
import { TooltipProvider, Toaster } from '@/components/ui';
import { queryClient } from '@/lib/queryClient';
import { router } from './router';
import { applyTheme, useThemeStore } from '@/stores/themeStore';
import '@/api/axiosClient'; // installs the mock adapter (§9.3) before any request

export function Providers() {
  // Keep the <html> theme class in sync with the persisted store on first mount.
  useEffect(() => {
    applyTheme(useThemeStore.getState().theme);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={200}>
        <RouterProvider router={router} />
        <Toaster />
        {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />}
      </TooltipProvider>
    </QueryClientProvider>
  );
}
