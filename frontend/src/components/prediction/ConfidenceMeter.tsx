import { Info } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Tooltip } from '@/components/ui';
import { CONFIDENCE_LABELS } from '@/lib/constants';
import type { ConfidenceBand } from '@/types/domain';

/**
 * ConfidenceMeter — §12.5. Three pips + a band label. Confidence reflects HOW
 * MUCH HISTORY the system has about a trainer, not how likely they are to
 * succeed. On LOW, the persistent amber note from §7.2 renders inline — not in a
 * tooltip, not dismissible.
 */
const FILLED: Record<ConfidenceBand, number> = { LOW: 1, MODERATE: 2, HIGH: 3 };
const PIP_TONE: Record<ConfidenceBand, string> = {
  LOW: 'bg-warning-fg',
  MODERATE: 'bg-warning-fg',
  HIGH: 'bg-success-fg',
};

const TOOLTIP =
  'Confidence reflects how much history the system has about this trainer — not how likely they are to succeed.';

export function ConfidenceMeter({
  band,
  showLabel = true,
  showNote = false,
  size = 'md',
  className,
}: {
  band: ConfidenceBand;
  showLabel?: boolean;
  showNote?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}) {
  const filled = FILLED[band];
  const pip = size === 'sm' ? 'h-1.5 w-4' : 'h-2 w-5';

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <Tooltip content={TOOLTIP}>
        <span className="inline-flex items-center gap-2">
          <span className="flex items-center gap-1" role="img" aria-label={`${CONFIDENCE_LABELS[band]} confidence`}>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className={cn('rounded-full', pip, i < filled ? PIP_TONE[band] : 'bg-primary-200 dark:bg-primary-700')}
              />
            ))}
          </span>
          {showLabel && (
            <span className="inline-flex items-center gap-1 font-mono text-label uppercase text-text-muted">
              {CONFIDENCE_LABELS[band]}
              <Info size={12} className="shrink-0 text-text-disabled" />
            </span>
          )}
        </span>
      </Tooltip>

      {showNote && band === 'LOW' && (
        <p className="rounded-sm border border-warning-border bg-warning-bg px-3 py-2 text-body-sm text-warning-fg" role="note">
          Limited history — this ranking leans on qualifications and availability rather than past
          performance.
        </p>
      )}
    </div>
  );
}
