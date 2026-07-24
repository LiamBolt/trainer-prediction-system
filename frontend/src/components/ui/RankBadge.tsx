import { cn } from '@/lib/cn';

/**
 * RankBadge — the numeric rank position in mono (§11.4). Rank 1 is styled
 * distinctly (brand fill), tying to the "TOP RANKED" treatment (FR-07).
 */
export interface RankBadgeProps {
  rank: number;
  className?: string;
  size?: 'sm' | 'md';
}

export function RankBadge({ rank, className, size = 'md' }: RankBadgeProps) {
  const isTop = rank === 1;
  const dim = size === 'sm' ? 'h-6 w-6 text-caption' : 'h-8 w-8 text-body-sm';
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full font-mono font-semibold tabular-nums',
        dim,
        isTop
          ? 'bg-brand text-brand-fg shadow-e1'
          : 'border border-strong bg-surface-sunken text-text-secondary',
        className,
      )}
      aria-label={`Rank ${rank}`}
    >
      {rank}
    </span>
  );
}
