import { Check, Circle, XCircle } from 'lucide-react';
import { cn } from '@/lib/cn';
import type { ProgrammeStatus } from '@/types/domain';

/**
 * ProgrammeTimeline — the swimlane journey of one request as a horizontal
 * stepper (§11.3): Created → Requirements set → Predicted → Approved →
 * Trainer responded → Conducted → Evaluated.
 */
const STEPS = [
  'Created',
  'Requirements set',
  'Predicted',
  'Approved',
  'Trainer responded',
  'Conducted',
  'Evaluated',
] as const;

const REACHED: Record<ProgrammeStatus, number> = {
  DRAFT: 1,
  REQUIREMENTS_SET: 2,
  PREDICTED: 3,
  AWAITING_RESPONSE: 4,
  ALLOCATED: 5,
  CONDUCTED: 6,
  EVALUATED: 7,
  CANCELLED: 0,
};

export function ProgrammeTimeline({ status }: { status: ProgrammeStatus }) {
  const reached = REACHED[status];
  const cancelled = status === 'CANCELLED';

  return (
    <ol className="flex flex-col gap-4 md:flex-row md:items-start md:gap-0">
      {STEPS.map((step, i) => {
        const index = i + 1;
        const done = !cancelled && index <= reached;
        const current = !cancelled && index === reached;
        return (
          <li key={step} className="flex flex-1 items-start gap-3 md:flex-col md:items-center md:text-center">
            <div className="flex items-center md:w-full">
              <span className="hidden h-px flex-1 bg-hairline md:block first:invisible" aria-hidden="true" />
              <span
                className={cn(
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-colors',
                  cancelled
                    ? 'border-danger-border bg-danger-bg text-danger-fg'
                    : done
                      ? 'border-brand bg-brand text-brand-fg'
                      : 'border-strong bg-surface text-text-disabled',
                  current && 'ring-2 ring-focus-ring ring-offset-2',
                )}
              >
                {cancelled ? (
                  <XCircle size={16} className="shrink-0" />
                ) : done ? (
                  <Check size={16} strokeWidth={3} className="shrink-0" />
                ) : (
                  <Circle size={8} className="shrink-0 fill-current" />
                )}
              </span>
              <span className="hidden h-px flex-1 bg-hairline md:block last:invisible" aria-hidden="true" />
            </div>
            <span
              className={cn(
                'text-body-sm md:mt-2',
                done ? 'font-medium text-ink' : 'text-text-muted',
              )}
            >
              {step}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
