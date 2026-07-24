import { useState } from 'react';
import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import { cn } from '@/lib/cn';
import { CRITERION_COLOR } from '@/lib/constants';
import { formatScore } from '@/lib/format';
import type { CriterionKey, CriterionScore } from '@/types/domain';

/**
 * ScoreLedger — the signature element (§4.7, §12.1). A horizontal segmented bar,
 * one segment per criterion, width ∝ contribution, filled from the criterion
 * colour ramp and separated by 1px canvas-coloured rules. The unearned remainder
 * to 100 is an unfilled track, so the viewer sees what was scored AND what was
 * available and missed. This is not a progress bar; it is an account of a decision.
 */
export interface ScoreLedgerProps {
  breakdown: CriterionScore[];
  total: number;
  size?: 'sm' | 'md'; // 10px list rows / 16px detail rail
  showTotal?: boolean;
  interactive?: boolean;
  className?: string;
}

export function ScoreLedger({
  breakdown,
  total,
  size = 'sm',
  showTotal = true,
  interactive = true,
  className,
}: ScoreLedgerProps) {
  const [hovered, setHovered] = useState<CriterionKey | null>(null);
  const barHeight = size === 'sm' ? 'h-2.5' : 'h-4';

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <TooltipPrimitive.Provider delayDuration={100}>
        <div
          className={cn(
            'relative flex-1 overflow-hidden rounded-full bg-primary-100 dark:bg-primary-800',
            barHeight,
          )}
          role="img"
          aria-label={`Suitability score ${formatScore(total)} out of 100`}
        >
          <div className="absolute inset-0 flex">
            {breakdown.map((c) => {
              const isDim = interactive && hovered !== null && hovered !== c.key;
              return (
                <TooltipPrimitive.Root key={c.key}>
                  <TooltipPrimitive.Trigger asChild>
                    <div
                      onMouseEnter={() => interactive && setHovered(c.key)}
                      onMouseLeave={() => interactive && setHovered(null)}
                      className="h-full transition-[width,opacity] duration-panel ease-entry"
                      style={{
                        width: `${c.contribution}%`,
                        background: CRITERION_COLOR[c.key],
                        opacity: isDim ? 0.35 : 1,
                        boxShadow: 'inset -1px 0 0 rgb(var(--canvas))',
                      }}
                    />
                  </TooltipPrimitive.Trigger>
                  <TooltipPrimitive.Portal>
                    <TooltipPrimitive.Content
                      side="top"
                      sideOffset={6}
                      className="z-50 rounded-sm border border-strong bg-primary-900 px-3 py-2 text-body-sm text-primary-50 shadow-e3 dark:bg-surface-raised dark:text-ink"
                    >
                      <span className="font-semibold">{c.label}</span>
                      <span className="mt-0.5 block font-mono text-label tabular-nums text-primary-200 dark:text-text-muted">
                        {formatScore(c.contribution)} of {c.weight} points
                      </span>
                      <span className="mt-1 block text-primary-100 dark:text-text-secondary">{c.rawValue}</span>
                      <TooltipPrimitive.Arrow className="fill-primary-900 dark:fill-surface-raised" />
                    </TooltipPrimitive.Content>
                  </TooltipPrimitive.Portal>
                </TooltipPrimitive.Root>
              );
            })}
          </div>
        </div>
      </TooltipPrimitive.Provider>

      {showTotal && (
        <span
          className={cn(
            'shrink-0 font-mono tabular-nums text-ink',
            size === 'sm' ? 'text-data-lg' : 'text-data-xl',
          )}
        >
          {formatScore(total)}
        </span>
      )}
    </div>
  );
}
