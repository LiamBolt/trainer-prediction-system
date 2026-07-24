import { memo } from 'react';
import { cn } from '@/lib/cn';
import { Avatar, RankBadge } from '@/components/ui';
import { ScoreLedger } from './ScoreLedger';
import { ConfidenceMeter } from './ConfidenceMeter';
import { RankDelta } from './RankDelta';
import { formatForceNumber } from '@/lib/format';
import type { Prediction, Trainer } from '@/types/domain';

/**
 * RankedTrainerRow — one candidate in the ranked list (§11.4). Rank 1 is visually
 * distinguished (FR-07): glass surface, a 1px brand ring, a TOP RANKED eyebrow,
 * and slightly increased height. Memoised so a weight change re-renders only rows
 * that actually moved.
 */
export interface RankedTrainerRowProps {
  prediction: Prediction;
  trainer: Trainer;
  selected: boolean;
  onSelect: () => void;
  /** oldRank − newRank from the last re-rank; drives the RankDelta badge. */
  delta: number;
}

function RankedTrainerRowBase({ prediction, trainer, selected, onSelect, delta }: RankedTrainerRowProps) {
  const isTop = prediction.rankPosition === 1;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        'flex w-full items-center gap-4 rounded-md border px-4 text-left transition-colors duration-default',
        isTop ? 'glass py-4 ring-1 ring-inset ring-primary-900 dark:ring-primary-300' : 'border-hairline bg-surface py-3',
        selected ? 'ring-2 ring-inset ring-focus-ring' : !isTop && 'hover:bg-surface-sunken',
      )}
    >
      <div className="flex shrink-0 items-center gap-2">
        <RankBadge rank={prediction.rankPosition} />
        <RankDelta delta={delta} />
      </div>

      <Avatar name={trainer.fullName} size={32} />

      <div className="flex min-w-0 flex-col">
        {isTop && (
          <span className="font-mono text-label uppercase text-brand">Top ranked</span>
        )}
        <span className="truncate text-h3 text-ink">
          {trainer.policeRank} {trainer.fullName}
        </span>
        <span className="truncate font-mono text-label text-text-muted">
          {formatForceNumber(trainer.forceNumber)} · {trainer.station}
        </span>
      </div>

      <div className="ml-auto flex min-w-0 flex-[2] items-center gap-4">
        <ScoreLedger
          breakdown={prediction.breakdown}
          total={prediction.predictionScore}
          size="sm"
          interactive={false}
          className="min-w-0 flex-1"
        />
        <ConfidenceMeter band={prediction.confidenceBand} showLabel={false} size="sm" />
      </div>
    </button>
  );
}

export const RankedTrainerRow = memo(RankedTrainerRowBase);
