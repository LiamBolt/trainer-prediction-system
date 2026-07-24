import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Card } from './Card';

/**
 * Stat — a KPI tile: `label` eyebrow, value in `data-xl` mono, optional delta.
 * Delta colour is semantic (up=success, down=danger) and always carries an icon
 * so it never reads by colour alone.
 */
export interface StatProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  delta?: { value: string; direction: 'up' | 'down' | 'flat' };
  icon?: React.ReactNode;
  className?: string;
  as?: 'card' | 'plain';
}

export function Stat({ label, value, hint, delta, icon, className, as = 'card' }: StatProps) {
  const body = (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-label uppercase text-text-muted">{label}</span>
        {icon && <span className="shrink-0 text-text-muted">{icon}</span>}
      </div>
      <div className="flex items-end gap-2">
        <span className="text-data-xl text-ink">{value}</span>
        {delta && (
          <span
            className={cn(
              'mb-1 inline-flex items-center gap-0.5 text-body-sm font-medium tabular-nums',
              delta.direction === 'up' && 'text-success-fg',
              delta.direction === 'down' && 'text-danger-fg',
              delta.direction === 'flat' && 'text-text-muted',
            )}
          >
            {delta.direction === 'up' && <ArrowUpRight size={16} className="shrink-0" />}
            {delta.direction === 'down' && <ArrowDownRight size={16} className="shrink-0" />}
            {delta.value}
          </span>
        )}
      </div>
      {hint && <span className="text-body-sm text-text-muted">{hint}</span>}
    </div>
  );

  if (as === 'plain') return <div className={className}>{body}</div>;
  return <Card className={cn('p-4 md:p-6', className)}>{body}</Card>;
}
