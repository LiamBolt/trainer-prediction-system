import { CRITERION_COLOR } from '@/lib/constants';
import { formatScore } from '@/lib/format';
import { Tooltip } from '@/components/ui';
import type { CriterionScore } from '@/types/domain';

/**
 * CriterionRow — §12.2. Per-criterion detail: colour swatch, name, raw value,
 * contribution out of weight (mono), a micro-bar, and a plain-English sentence.
 * A MISSING dataQuality shows an amber dot — never a silent default substitution.
 */
export function CriterionRow({ criterion }: { criterion: CriterionScore }) {
  const pct = Math.max(0, Math.min(100, criterion.normalized));
  return (
    <div className="flex flex-col gap-1.5 py-3">
      <div className="flex items-center gap-2">
        <span
          className="h-3 w-3 shrink-0 rounded-sm"
          style={{ background: CRITERION_COLOR[criterion.key] }}
          aria-hidden="true"
        />
        <span className="flex-1 text-body font-semibold text-ink">{criterion.label}</span>
        {criterion.dataQuality === 'MISSING' && (
          <Tooltip content="No evaluations recorded; a neutral score was used.">
            <span
              className="h-2 w-2 shrink-0 rounded-full bg-warning-fg"
              role="img"
              aria-label="Limited data"
            />
          </Tooltip>
        )}
        <span className="shrink-0 font-mono text-data tabular-nums text-text-secondary">
          {formatScore(criterion.contribution)}
          <span className="text-text-disabled"> / {criterion.weight}</span>
        </span>
      </div>

      {/* micro-bar (normalised 0–100) */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-primary-100 dark:bg-primary-800">
        <div
          className="h-full rounded-full transition-[width] duration-panel ease-entry"
          style={{ width: `${pct}%`, background: CRITERION_COLOR[criterion.key] }}
        />
      </div>

      <p className="text-body-sm text-text-muted">{criterion.explanation}</p>
    </div>
  );
}
