import { NavLink } from 'react-router-dom';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { cn } from '@/lib/cn';
import { navForRole, type NavItem } from '@/lib/nav';
import { Tooltip } from '@/components/ui';
import { Wordmark } from '@/components/brand/Wordmark';
import type { RoleName } from '@/types/domain';

/**
 * Sidebar — 264px expanded / 72px collapsed (§10.3). Role-filtered nav grouped
 * with label-type headings. The active item carries a 4px left bar that grows
 * from 0 and a tint that fades in over 180ms. Below 1024px AppShell renders this
 * inside a drawer instead.
 */
export interface SidebarProps {
  role: RoleName | null;
  collapsed: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: () => void;
  /** In the mobile drawer the collapse control and brand are hidden. */
  variant?: 'desktop' | 'drawer';
}

function NavRow({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  const row = (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'group relative flex h-10 items-center gap-3 rounded-sm text-body font-medium transition-colors duration-default ease-entry',
          collapsed ? 'justify-center px-0' : 'px-3',
          isActive
            ? 'bg-surface-sunken text-ink'
            : 'text-text-secondary hover:bg-surface-sunken hover:text-ink',
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            aria-hidden="true"
            className={cn(
              'absolute left-0 top-1.5 bottom-1.5 w-1 origin-left rounded-r-full bg-primary-900 transition-transform duration-default ease-entry dark:bg-primary-300',
              isActive ? 'scale-x-100' : 'scale-x-0',
            )}
          />
          <Icon size={20} className="shrink-0" />
          {!collapsed && <span className="truncate">{item.label}</span>}
        </>
      )}
    </NavLink>
  );

  if (collapsed) {
    return (
      <Tooltip content={item.label} side="right">
        {row}
      </Tooltip>
    );
  }
  return row;
}

export function Sidebar({
  role,
  collapsed,
  onToggleCollapse,
  onNavigate,
  variant = 'desktop',
}: SidebarProps) {
  const sections = navForRole(role);

  return (
    <div
      className={cn(
        'flex h-full flex-col border-r border-hairline bg-surface',
        variant === 'desktop' && (collapsed ? 'w-sidebar-collapsed' : 'w-sidebar'),
        variant === 'drawer' && 'w-full',
      )}
    >
      {variant === 'drawer' && (
        <div className="flex h-app-bar shrink-0 items-center border-b border-hairline px-4 text-ink">
          <Wordmark variant="full" />
        </div>
      )}

      <nav className="flex-1 overflow-y-auto p-3" aria-label="Primary">
        <div className="flex flex-col gap-6">
          {sections.map((section) => (
            <div key={section.heading} className="flex flex-col gap-1">
              {!collapsed && (
                <span className="px-3 pb-1 font-mono text-label uppercase text-text-muted">
                  {section.heading}
                </span>
              )}
              {section.items.map((item) => (
                <NavRow key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />
              ))}
            </div>
          ))}
        </div>
      </nav>

      {variant === 'desktop' && onToggleCollapse && (
        <div className="shrink-0 border-t border-hairline p-3">
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className={cn(
              'flex h-10 w-full items-center gap-3 rounded-sm text-body font-medium text-text-secondary transition-colors hover:bg-surface-sunken hover:text-ink',
              collapsed ? 'justify-center px-0' : 'px-3',
            )}
          >
            {collapsed ? (
              <PanelLeftOpen size={20} className="shrink-0" />
            ) : (
              <PanelLeftClose size={20} className="shrink-0" />
            )}
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      )}
    </div>
  );
}
