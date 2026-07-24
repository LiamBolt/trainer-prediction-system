import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, Menu, Moon, Search, Sun, LogOut, UserCircle, Settings, Repeat } from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  Avatar,
  Badge,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  IconButton,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Button,
} from '@/components/ui';
import { Wordmark } from '@/components/brand/Wordmark';
import { useThemeStore } from '@/stores/themeStore';
import { useUiStore } from '@/stores/uiStore';
import { useAuth } from '@/hooks/useAuth';
import { ROLE_LABELS } from '@/lib/constants';
import { notificationsApi } from '@/api/endpoints';
import { formatRelative } from '@/lib/format';
import type { RoleName } from '@/types/domain';

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';
const ROLE_ORDER: RoleName[] = [
  'TRAINING_ADMINISTRATOR',
  'TRAINING_OFFICER',
  'TRAINER',
  'SYSTEM_ADMINISTRATOR',
];

export function TopBar({ onOpenMobileNav }: { onOpenMobileNav: () => void }) {
  const { theme, toggle } = useThemeStore();
  const setCommandOpen = useUiStore((s) => s.setCommandOpen);
  const { user, role, signOut, switchRole } = useAuth();
  const queryClient = useQueryClient();

  const recipientId = user?.userId;
  const { data: notifications = [] } = useQuery({
    queryKey: ['notifications', recipientId],
    queryFn: () => notificationsApi.listNotifications(recipientId),
    enabled: Boolean(user),
  });
  const unread = notifications.filter((n) => n.status === 'UNREAD').length;

  const markAllRead = async () => {
    await notificationsApi.markAllNotificationsRead(recipientId);
    queryClient.invalidateQueries({ queryKey: ['notifications'] });
  };

  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex h-app-bar shrink-0 items-center gap-3 border-b border-hairline px-4 text-ink md:px-6',
        theme === 'dark' ? 'glass' : 'bg-surface',
      )}
    >
      {/* Mobile nav toggle */}
      <IconButton label="Open menu" variant="ghost" onClick={onOpenMobileNav} className="lg:hidden">
        <Menu size={20} className="shrink-0" />
      </IconButton>

      <Link to="/dashboard" className="flex items-center rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
        <Wordmark variant="full" className="hidden sm:flex" />
        <Wordmark variant="compact" className="sm:hidden" />
      </Link>

      {/* Global search -> command palette */}
      <button
        type="button"
        onClick={() => setCommandOpen(true)}
        className="ml-2 hidden h-9 w-full max-w-sm items-center gap-2 rounded-sm border border-strong bg-surface-sunken px-3 text-body-sm text-text-muted transition-colors hover:text-ink md:flex"
      >
        <Search size={16} className="shrink-0" />
        <span className="flex-1 text-left">Search or jump to…</span>
        <kbd className="rounded border border-hairline bg-surface px-1.5 py-0.5 font-mono text-label text-text-muted">
          ⌘K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-1 md:gap-2">
        <IconButton label="Search" variant="ghost" onClick={() => setCommandOpen(true)} className="md:hidden">
          <Search size={20} className="shrink-0" />
        </IconButton>

        {/* Demo role switcher — mocks only (§8.9) */}
        {USE_MOCKS && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" icon={<Repeat size={16} className="shrink-0" />} className="hidden sm:inline-flex">
                <span className="font-mono text-label uppercase">Demo role</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent glass>
              <DropdownMenuLabel>Switch role (demo)</DropdownMenuLabel>
              {ROLE_ORDER.map((r) => (
                <DropdownMenuItem key={r} onSelect={() => void switchRole(r)}>
                  {ROLE_LABELS[r]}
                  {role === r && <span className="ml-auto font-mono text-label text-brand">Current</span>}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        {/* Theme toggle */}
        <IconButton label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'} variant="ghost" onClick={toggle}>
          <span className="relative flex h-5 w-5 items-center justify-center">
            <Sun
              size={20}
              className={cn('absolute shrink-0 transition-all duration-default', theme === 'dark' ? 'rotate-90 opacity-0' : 'rotate-0 opacity-100')}
            />
            <Moon
              size={20}
              className={cn('absolute shrink-0 transition-all duration-default', theme === 'dark' ? 'rotate-0 opacity-100' : '-rotate-90 opacity-0')}
            />
          </span>
        </IconButton>

        {/* Notifications */}
        <Popover>
          <PopoverTrigger asChild>
            <span className="relative inline-flex">
              <IconButton label={`Notifications${unread ? `, ${unread} unread` : ''}`} variant="ghost">
                <Bell size={20} className="shrink-0" />
              </IconButton>
              {unread > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger-fg px-1 font-mono text-label font-semibold leading-none text-canvas">
                  {unread}
                </span>
              )}
            </span>
          </PopoverTrigger>
          <PopoverContent glass align="end" className="w-80 p-0">
            <div className="flex items-center justify-between border-b border-hairline p-3">
              <span className="font-mono text-label uppercase text-text-muted">Notifications</span>
              {unread > 0 && (
                <button type="button" onClick={markAllRead} className="text-body-sm text-brand hover:underline">
                  Mark all read
                </button>
              )}
            </div>
            <div className="max-h-80 overflow-y-auto">
              {notifications.slice(0, 6).map((n) => (
                <Link
                  key={n.notificationId}
                  to={n.linkTo ?? '/notifications'}
                  className="flex gap-3 border-b border-hairline p-3 last:border-b-0 hover:bg-surface-sunken"
                >
                  <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', n.status === 'UNREAD' ? 'bg-brand' : 'bg-transparent')} />
                  <span className="flex flex-col gap-0.5">
                    <span className="text-body-sm text-ink">{n.message}</span>
                    <span className="font-mono text-label text-text-muted">{formatRelative(n.sentDate)}</span>
                  </span>
                </Link>
              ))}
              {notifications.length === 0 && (
                <p className="p-6 text-center text-body-sm text-text-muted">No notifications.</p>
              )}
            </div>
            <div className="border-t border-hairline p-2">
              <Link to="/notifications" className="block rounded-sm px-2 py-1.5 text-center text-body-sm text-brand hover:bg-surface-sunken">
                View all
              </Link>
            </div>
          </PopoverContent>
        </Popover>

        {/* User menu */}
        {user && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className="flex items-center gap-2 rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
                <Avatar name={user.fullName} size={32} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent glass className="w-64">
              <div className="flex items-center gap-3 p-2">
                <Avatar name={user.fullName} size={40} />
                <div className="flex min-w-0 flex-col">
                  <span className="truncate text-body font-semibold text-ink">{user.fullName}</span>
                  {role && (
                    <Badge tone="info" dot={false} className="mt-1 w-fit">
                      {ROLE_LABELS[role]}
                    </Badge>
                  )}
                </div>
              </div>
              <DropdownMenuSeparator />
              {role === 'TRAINER' && (
                <DropdownMenuItem asChild>
                  <Link to="/my-profile">
                    <UserCircle size={16} className="shrink-0" />
                    My profile
                  </Link>
                </DropdownMenuItem>
              )}
              <DropdownMenuItem asChild>
                <Link to="/settings">
                  <Settings size={16} className="shrink-0" />
                  Settings
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem tone="danger" onSelect={() => void signOut()}>
                <LogOut size={16} className="shrink-0" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </header>
  );
}
