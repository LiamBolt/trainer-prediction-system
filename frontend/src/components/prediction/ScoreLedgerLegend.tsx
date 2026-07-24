import { CRITERION_COLOR } from '@/lib/constants';
import { formatScore } from '@/lib/format';
import type { CriterionScore } from '@/types/domain';

/**
 * ScoreLedgerLegend — §12.1. Compact key for the ledger: colour swatch, name,
 * contribution/weight in mono, and a micro-bar. Colour is never the only signal.
 */
export function ScoreLedgerLegend({ breakdown }: { breakdown: CriterionScore[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {breakdown.map((c) => (
        <li key={c.key} className="flex items-center gap-2">
          <span
            className="h-3 w-3 shrink-0 rounded-sm"
            style={{ background: CRITERION_COLOR[c.key] }}
            aria-hidden="true"
          />
          <span className="flex-1 truncate text-body-sm text-text-secondary">{c.label}</span>
          <span className="font-mono text-label tabular-nums text-text-muted">
            {formatScore(c.contribution)} / {c.weight}
          </span>
        </li>
      ))}
    </ul>
  );
}
