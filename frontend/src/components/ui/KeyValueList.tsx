import { cn } from '@/lib/cn';

/**
 * KeyValueList — the detail-page workhorse (§10.1). Label column in `label` type
 * (mono uppercase), value column in body or data, baselines aligned.
 */
export interface KeyValueItem {
  label: string;
  value: React.ReactNode;
  /** Render the value in the mono data face (identifiers, figures). */
  mono?: boolean;
}

export function KeyValueList({
  items,
  className,
  columns = 1,
}: {
  items: KeyValueItem[];
  className?: string;
  columns?: 1 | 2;
}) {
  return (
    <dl
      className={cn(
        'grid gap-x-8 gap-y-4',
        columns === 2 ? 'sm:grid-cols-2' : 'grid-cols-1',
        className,
      )}
    >
      {items.map((item, i) => (
        <div
          key={`${item.label}-${i}`}
          className="grid grid-cols-[minmax(0,140px)_1fr] items-baseline gap-4"
        >
          <dt className="pt-0.5 font-mono text-label uppercase text-text-muted">{item.label}</dt>
          <dd className={cn('text-body text-ink', item.mono && 'font-mono tabular-nums')}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
