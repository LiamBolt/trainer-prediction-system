import { Suspense, useMemo, useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { ErrorBoundary } from '@/components/feedback/ErrorBoundary';
import { RouteSkeleton } from '@/components/feedback/RouteSkeleton';
import { LayoutDashboard, Plus, LogOut, Sun } from 'lucide-react';
import { Drawer, DrawerContent, CommandPalette, type PaletteGroup } from '@/components/ui';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { ClassificationBar } from './ClassificationBar';
import { useUiStore } from '@/stores/uiStore';
import { useThemeStore } from '@/stores/themeStore';
import { useAuth } from '@/hooks/useAuth';
import { useKeyboardShortcut } from '@/hooks/useKeyboardShortcut';
import { navForRole } from '@/lib/nav';

/**
 * AppShell — sidebar + top bar + content (§5.1, §10.3). The content region owns
 * the gutter: 32px ≥1280, 24px 1024–1279, 16px below, always equal left/right,
 * centred at max 1440px. Below 1024px the sidebar becomes a glass drawer.
 */
export function AppShell() {
  const navigate = useNavigate();
  const { role, signOut } = useAuth();
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const commandOpen = useUiStore((s) => s.commandOpen);
  const setCommandOpen = useUiStore((s) => s.setCommandOpen);
  const toggleTheme = useThemeStore((s) => s.toggle);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useKeyboardShortcut('k', () => setCommandOpen(true), { meta: true, allowInInputs: true });

  const paletteGroups = useMemo<PaletteGroup[]>(() => {
    const sections = navForRole(role);
    const goTo: PaletteGroup = {
      heading: 'Go to',
      commands: sections.flatMap((s) =>
        s.items.map((item) => ({
          id: `nav-${item.to}`,
          label: item.label,
          keywords: s.heading,
          icon: <item.icon size={16} className="shrink-0" />,
          run: () => navigate(item.to),
        })),
      ),
    };
    const actions: PaletteGroup = {
      heading: 'Actions',
      commands: [
        ...(role === 'TRAINING_ADMINISTRATOR' || role === 'TRAINING_OFFICER'
          ? [
              {
                id: 'action-new-request',
                label: 'Create training request',
                icon: <Plus size={16} className="shrink-0" />,
                run: () => navigate('/programmes/new'),
              },
            ]
          : []),
        {
          id: 'action-dashboard',
          label: 'Go to dashboard',
          icon: <LayoutDashboard size={16} className="shrink-0" />,
          run: () => navigate('/dashboard'),
        },
        {
          id: 'action-theme',
          label: 'Toggle light / dark theme',
          icon: <Sun size={16} className="shrink-0" />,
          run: () => toggleTheme(),
        },
        {
          id: 'action-signout',
          label: 'Sign out',
          icon: <LogOut size={16} className="shrink-0" />,
          run: () => void signOut(),
        },
      ],
    };
    return [goTo, actions];
  }, [role, navigate, toggleTheme, signOut]);

  return (
    <div className="flex h-dvh flex-col bg-canvas">
      <TopBar onOpenMobileNav={() => setMobileNavOpen(true)} />

      <div className="flex min-h-0 flex-1">
        <aside className="hidden shrink-0 lg:block">
          <Sidebar role={role} collapsed={sidebarCollapsed} onToggleCollapse={toggleSidebar} />
        </aside>

        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-content px-4 py-8 lg:px-6 xl:px-8">
            {/* Route-shaped skeleton while a lazy route chunk loads (§9.4). */}
            <ErrorBoundary>
              <Suspense fallback={<RouteSkeleton />}>
                <Outlet />
              </Suspense>
            </ErrorBoundary>
          </div>
        </main>
      </div>

      <ClassificationBar className="shrink-0" />

      {/* Mobile nav drawer (< 1024px) */}
      <Drawer open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <DrawerContent side="left" width="sm" showClose={false} className="p-0">
          <Sidebar
            role={role}
            collapsed={false}
            variant="drawer"
            onNavigate={() => setMobileNavOpen(false)}
          />
        </DrawerContent>
      </Drawer>

      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} groups={paletteGroups} />
    </div>
  );
}
