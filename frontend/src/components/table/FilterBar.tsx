import { Search, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Input } from '@/components/ui';

/**
 * FilterBar — the search + filter control cluster above list tables. Screens
 * compose their own selects/date-ranges via `children`. Filter state lives in the
 * URL at the call site (§9.2), so a shared URL reproduces the exact view.
 */
export function FilterBar({
  search,
  onSearchChange,
  searchPlaceholder = 'Search…',
  children,
  onClear,
  hasActiveFilters,
  actions,
  className,
}: {
  search?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  children?: React.ReactNode;
  onClear?: () => void;
  hasActiveFilters?: boolean;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center', className)}>
      {onSearchChange && (
        <div className="w-full sm:max-w-xs">
          <Input
            value={search ?? ''}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            leading={<Search size={16} className="shrink-0" />}
            aria-label="Search"
          />
        </div>
      )}
      {children}
      {hasActiveFilters && onClear && (
        <button
          type="button"
          onClick={onClear}
          className="inline-flex h-9 items-center gap-1 rounded-sm px-2 text-body-sm text-text-muted transition-colors hover:text-ink"
        >
          <X size={14} className="shrink-0" />
          Clear filters
        </button>
      )}
      {actions && <div className="sm:ml-auto flex items-center gap-2">{actions}</div>}
    </div>
  );
}
