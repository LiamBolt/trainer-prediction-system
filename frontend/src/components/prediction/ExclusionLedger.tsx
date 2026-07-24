import { useState } from 'react';
import { ChevronDown, UserX } from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Avatar,
  Badge,
} from '@/components/ui';
import { formatCount, formatForceNumber } from '@/lib/format';
import type { ExcludedTrainer, ExclusionReason, PredictionRun } from '@/types/domain';

/**
 * ExclusionLedger — §12.4. Trainers who were filtered out are as informative as
 * those ranked. Collapsed by default; each reason group expands to names, ranks,
 * force numbers, and the specific reason. This answers, inside the product, the
 * question every Administrator eventually asks by phone today.
 */
const REASON_LABEL: Record<ExclusionReason, string> = {
  UNAVAILABLE: 'unavailable for these dates',
  MISSING_SPECIALIZATION: 'do not hold the required specialisation',
  SCHEDULE_CONFLICT: 'already assigned to overlapping training',
  BELOW_MINIMUM_EXPERIENCE: 'below the minimum experience set for this request',
  BELOW_MINIMUM_QUALIFICATION: 'below the minimum qualification set for this request',
};
const REASON_RULE: Record<ExclusionReason, string> = {
  UNAVAILABLE: 'BR-03',
  MISSING_SPECIALIZATION: 'BR-04',
  SCHEDULE_CONFLICT: 'BR-03',
  BELOW_MINIMUM_EXPERIENCE: 'FR-05',
  BELOW_MINIMUM_QUALIFICATION: 'FR-05',
};
const REASON_ORDER: ExclusionReason[] = [
  'UNAVAILABLE',
  'MISSING_SPECIALIZATION',
  'SCHEDULE_CONFLICT',
  'BELOW_MINIMUM_EXPERIENCE',
  'BELOW_MINIMUM_QUALIFICATION',
];

export function ExclusionLedger({ run }: { run: PredictionRun }) {
  const [open, setOpen] = useState(false);
  const groups = REASON_ORDER.map((reason) => ({
    reason,
    trainers: run.excluded.filter((t) => t.reason === reason),
  })).filter((g) => g.trainers.length > 0);

  if (run.excludedCount === 0) return null;

  return (
    <section className="rounded-md border border-hairline bg-surface shadow-e1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 p-4 text-left md:p-6"
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-text-muted">
          <UserX size={20} className="shrink-0" />
        </span>
        <span className="flex flex-1 flex-col">
          <span className="text-h3 text-ink">
            {formatCount(run.excludedCount)} of {formatCount(run.candidatePoolSize)} trainers were
            not considered
          </span>
          <span className="text-body-sm text-text-muted">
            Grouped by the rule that excluded them. Nothing is hidden — every trainer is accountable.
          </span>
        </span>
        <ChevronDown
          size={20}
          className={cn('shrink-0 text-text-muted transition-transform duration-panel', open && 'rotate-180')}
        />
      </button>

      {open && (
        <div className="border-t border-hairline px-4 pb-2 md:px-6">
          <Accordion type="multiple">
            {groups.map((g) => (
              <AccordionItem key={g.reason} value={g.reason}>
                <AccordionTrigger>
                  <span className="flex items-center gap-3">
                    <span className="font-mono text-data font-semibold tabular-nums text-ink">
                      {formatCount(g.trainers.length)}
                    </span>
                    <span className="font-normal text-text-secondary">{REASON_LABEL[g.reason]}</span>
                    <Badge tone="neutral" dot={false} mono>
                      {REASON_RULE[g.reason]}
                    </Badge>
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <ul className="flex flex-col divide-y divide-hairline">
                    {g.trainers.slice(0, 40).map((t) => (
                      <ExcludedRow key={t.trainerId} trainer={t} />
                    ))}
                    {g.trainers.length > 40 && (
                      <li className="py-2 text-body-sm text-text-muted">
                        … and {formatCount(g.trainers.length - 40)} more.
                      </li>
                    )}
                  </ul>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      )}
    </section>
  );
}

function ExcludedRow({ trainer }: { trainer: ExcludedTrainer }) {
  return (
    <li className="flex items-center gap-3 py-2">
      <Avatar name={trainer.fullName} size={24} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-body-sm font-medium text-ink">
          {trainer.policeRank} {trainer.fullName}
        </span>
        <span className="truncate font-mono text-label text-text-muted">
          {formatForceNumber(trainer.forceNumber)} · {trainer.reasonDetail}
        </span>
      </span>
    </li>
  );
}
