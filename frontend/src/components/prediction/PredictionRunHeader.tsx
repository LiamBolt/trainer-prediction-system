import { RotateCw, SlidersHorizontal, Users, Timer } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui';
import { formatCount, formatElapsed } from '@/lib/format';
import type { PredictionRun } from '@/types/domain';

/**
 * PredictionRunHeader — §11.4. Candidate pool, excluded count, ranked count, and
 * the elapsed run time in mono (tied to NFR-01), plus a weight-source chip and a
 * Re-run action.
 */
export function PredictionRunHeader({
  run,
  simulated,
  onRerun,
  onOpenStudio,
  rerunning,
  canTune,
}: {
  run: PredictionRun;
  simulated: boolean;
  onRerun: () => void;
  onOpenStudio?: () => void;
  rerunning?: boolean;
  canTune?: boolean;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-md border border-hairline bg-surface p-4 shadow-e1 md:flex-row md:items-center md:justify-between md:p-6">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <Metric icon={<Users size={16} className="shrink-0" />} value={formatCount(run.candidatePoolSize)} label="considered" />
        <Metric value={formatCount(run.excludedCount)} label="excluded" />
        <Metric value={formatCount(run.rankedCount)} label="ranked" tone="ink" />
        <Metric icon={<Timer size={16} className="shrink-0" />} value={`computed in ${formatElapsed(run.elapsedMs)}`} label="" />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span
          className={cn(
            'inline-flex h-badge items-center gap-1.5 rounded-full border px-2 font-mono text-label uppercase',
            simulated
              ? 'border-warning-border bg-warning-bg text-warning-fg'
              : 'border-hairline bg-surface-sunken text-text-secondary',
          )}
        >
          <span className={cn('h-1.5 w-1.5 rounded-full', simulated ? 'bg-warning-fg' : 'bg-text-muted')} />
          {simulated ? 'Simulated weights' : 'Standard policy weights'}
        </span>
        {canTune && onOpenStudio && (
          <Button variant="secondary" size="sm" onClick={onOpenStudio} icon={<SlidersHorizontal size={16} className="shrink-0" />}>
            Weight studio
          </Button>
        )}
        <Button variant="secondary" size="sm" onClick={onRerun} loading={rerunning} icon={<RotateCw size={16} className="shrink-0" />}>
          Re-run
        </Button>
      </div>
    </div>
  );
}

function Metric({
  icon,
  value,
  label,
  tone = 'secondary',
}: {
  icon?: React.ReactNode;
  value: string;
  label: string;
  tone?: 'secondary' | 'ink';
}) {
  return (
    <div className="flex items-center gap-2">
      {icon && <span className="text-text-muted">{icon}</span>}
      <span className={cn('font-mono text-data tabular-nums', tone === 'ink' ? 'font-semibold text-ink' : 'text-text-secondary')}>
        {value}
      </span>
      {label && <span className="text-body-sm text-text-muted">{label}</span>}
    </div>
  );
}
