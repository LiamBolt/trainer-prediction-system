/* eslint-disable react-refresh/only-export-components -- variants/hooks are intentionally co-located with their component; this rule only affects dev-time Fast Refresh. */
import { Toaster as SonnerToaster, toast } from 'sonner';
import { useThemeStore } from '@/stores/themeStore';

/**
 * Toaster — sonner, themed to match the app. Toasts announce the consequence of
 * an action in the same verb the button used (§12.8) and are aria-live polite.
 */
export function Toaster() {
  const theme = useThemeStore((s) => s.resolved);
  return (
    <SonnerToaster
      theme={theme}
      position="bottom-right"
      closeButton
      toastOptions={{
        classNames: {
          toast:
            'group rounded-md border border-hairline bg-surface text-ink shadow-e3 font-sans text-body',
          description: 'text-body-sm text-text-muted',
          actionButton: 'bg-brand text-brand-fg',
          cancelButton: 'bg-surface-sunken text-text-secondary',
        },
      }}
    />
  );
}

export { toast };
