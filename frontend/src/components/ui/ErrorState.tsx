import { AlertTriangle, RotateCw } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Button } from './Button';

/**
 * ErrorState — §5.7. What went wrong plus a Retry. Never a blank page, never a
 * raw error object (§14.4). Rendered inside the surface that failed.
 */
export interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'We could not load this. Please try again.',
  onRetry,
  className,
  compact,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center text-center',
        compact ? 'gap-2 py-8' : 'gap-3 py-16',
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-bg text-danger-fg">
        <AlertTriangle size={20} className="shrink-0" />
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="text-h3 text-ink">{title}</h3>
        <p className="mx-auto max-w-md text-body text-text-muted">{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry} icon={<RotateCw size={16} className="shrink-0" />} className="mt-2">
          Try again
        </Button>
      )}
    </div>
  );
}
