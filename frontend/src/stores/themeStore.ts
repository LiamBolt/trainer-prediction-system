import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * themeStore — D2. Light is the default; dark is a first-class toggle. Persisted.
 * prefers-color-scheme is respected on first visit only (i.e. when nothing has
 * been persisted yet). Applying the `.dark` class is centralised here.
 */
export type Theme = 'light' | 'dark';

interface ThemeState {
  theme: Theme;
  resolved: Theme;
  setTheme: (theme: Theme) => void;
  toggle: () => void;
}

function systemPrefersDark(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );
}

export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return;
  document.documentElement.classList.toggle('dark', theme === 'dark');
}

const initialTheme: Theme = systemPrefersDark() ? 'dark' : 'light';

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: initialTheme,
      resolved: initialTheme,
      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme, resolved: theme });
      },
      toggle: () => {
        const next: Theme = get().theme === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        set({ theme: next, resolved: next });
      },
    }),
    {
      name: 'tps-theme',
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme);
      },
    },
  ),
);
