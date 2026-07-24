import { cn } from '@/lib/cn';

/**
 * EmptyState — §5.7 / §12.8. A sentence explaining what will appear here and an
 * action that creates it. Gives direction, never mood ("No … yet. Create one to
 * start…", never "Oops!").
 */
export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  compact?: boolean;
}

export function EmptyState({ icon, title, description, action, className, compact }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center',
        compact ? 'gap-2 py-8' : 'gap-3 py-16',
        className,
      )}
    >
      {icon && (
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-sunken text-text-muted">
          {icon}
        </div>
      )}
      <div className="flex flex-col gap-1">
        <h3 className="text-h3 text-ink">{title}</h3>
        {description && (
          <p className="mx-auto max-w-md text-body text-text-muted">{description}</p>
        )}
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
