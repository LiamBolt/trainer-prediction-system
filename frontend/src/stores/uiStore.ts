import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * uiStore — global UI chrome state (§9.2). Sidebar collapse is persisted; the
 * command-palette open flag and plain-language toggle live here too.
 */
interface UiState {
  sidebarCollapsed: boolean;
  commandOpen: boolean;
  plainLanguage: boolean; // §12.8 — default on
  reduceMotion: boolean; // §11.11 accessibility override
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
  setCommandOpen: (v: boolean) => void;
  setPlainLanguage: (v: boolean) => void;
  setReduceMotion: (v: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      commandOpen: false,
      plainLanguage: true,
      reduceMotion: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      setCommandOpen: (v) => set({ commandOpen: v }),
      setPlainLanguage: (v) => set({ plainLanguage: v }),
      setReduceMotion: (v) => set({ reduceMotion: v }),
    }),
    {
      name: 'tps-ui',
      // commandOpen is ephemeral — never persist it.
      partialize: (s) => ({
        sidebarCollapsed: s.sidebarCollapsed,
        plainLanguage: s.plainLanguage,
        reduceMotion: s.reduceMotion,
      }),
    },
  ),
);
