import { Breadcrumbs, type Crumb } from '@/components/ui';
import { cn } from '@/lib/cn';

/**
 * PageHeader — used by EVERY page so titles land on the same baseline (§10.3).
 * Breadcrumbs, an optional mono eyebrow, the h1 title, a description, and a
 * right-aligned action cluster. 32px below the app bar is owned by AppShell.
 */
export interface PageHeaderProps {
  title: string;
  eyebrow?: string;
  description?: React.ReactNode;
  breadcrumbs?: Crumb[];
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  eyebrow,
  description,
  breadcrumbs,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {breadcrumbs && breadcrumbs.length > 0 && <Breadcrumbs items={breadcrumbs} />}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="flex min-w-0 flex-col gap-1">
          {eyebrow && <span className="font-mono text-label uppercase text-text-muted">{eyebrow}</span>}
          <h1 className="text-h1 text-ink">{title}</h1>
          {description && <p className="max-w-2xl text-body text-text-muted">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-3">{actions}</div>}
      </div>
    </div>
  );
}
