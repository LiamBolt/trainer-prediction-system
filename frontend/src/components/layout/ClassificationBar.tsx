import { cn } from '@/lib/cn';
import { CLASSIFICATION_LEFT, CLASSIFICATION_RIGHT } from '@/lib/constants';

/**
 * ClassificationBar — the slim government-classification strip at the very bottom
 * of the viewport (§10.3). Present on every authenticated screen and the landing
 * page. The detail that makes this read as a real restricted system.
 */
export function ClassificationBar({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'flex h-classification items-center justify-between gap-4 border-t border-hairline bg-surface px-4 md:px-6',
        className,
      )}
    >
      <span className="truncate font-mono text-label uppercase text-text-muted">
        {CLASSIFICATION_LEFT}
      </span>
      <span className="hidden truncate font-mono text-label uppercase text-text-muted sm:inline">
        {CLASSIFICATION_RIGHT}
      </span>
    </div>
  );
}
