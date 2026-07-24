import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatCount } from '@/lib/format';

export interface PaginationProps {
  page: number; // 1-based
  pageCount: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  className?: string;
}

/** Compact page numbers with a first/last window and an item-range summary. */
function pageWindow(page: number, pageCount: number): (number | 'gap')[] {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i + 1);
  const out: (number | 'gap')[] = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(pageCount - 1, page + 1);
  if (start > 2) out.push('gap');
  for (let i = start; i <= end; i++) out.push(i);
  if (end < pageCount - 1) out.push('gap');
  out.push(pageCount);
  return out;
}

export function Pagination({
  page,
  pageCount,
  total,
  pageSize,
  onPageChange,
  className,
}: PaginationProps) {
  if (pageCount <= 1) {
    return (
      <div className={cn('flex items-center justify-between text-body-sm text-text-muted', className)}>
        <span className="tabular-nums">{formatCount(total)} results</span>
      </div>
    );
  }
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  const navBtn =
    'inline-flex h-8 min-w-8 items-center justify-center rounded-sm px-2 text-body-sm tabular-nums transition-colors ' +
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
    'disabled:cursor-not-allowed disabled:opacity-40';

  return (
    <div className={cn('flex flex-wrap items-center justify-between gap-3', className)}>
      <span className="text-body-sm tabular-nums text-text-muted">
        Showing {formatCount(from)}–{formatCount(to)} of {formatCount(total)}
      </span>
      <nav className="flex items-center gap-1" aria-label="Pagination">
        <button
          type="button"
          className={cn(navBtn, 'text-text-secondary hover:bg-surface-sunken')}
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft size={16} className="shrink-0" />
        </button>
        {pageWindow(page, pageCount).map((p, i) =>
          p === 'gap' ? (
            <span key={`gap-${i}`} className="px-1 text-text-disabled">
              …
            </span>
          ) : (
            <button
              key={p}
              type="button"
              aria-current={p === page ? 'page' : undefined}
              onClick={() => onPageChange(p)}
              className={cn(
                navBtn,
                p === page
                  ? 'bg-brand text-brand-fg'
                  : 'text-text-secondary hover:bg-surface-sunken',
              )}
            >
              {p}
            </button>
          ),
        )}
        <button
          type="button"
          className={cn(navBtn, 'text-text-secondary hover:bg-surface-sunken')}
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pageCount}
          aria-label="Next page"
        >
          <ChevronRight size={16} className="shrink-0" />
        </button>
      </nav>
    </div>
  );
}
