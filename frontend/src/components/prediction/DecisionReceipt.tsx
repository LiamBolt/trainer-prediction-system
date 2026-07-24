import { forwardRef } from 'react';
import { cn } from '@/lib/cn';
import { Crest } from '@/components/brand/Crest';
import { ScoreLedger } from './ScoreLedger';
import { CriterionRow } from './CriterionRow';
import { KeyValueList } from '@/components/ui';
import { formatForceNumber, formatTimestamp, ordinal } from '@/lib/format';
import { CRITERION_META } from '@/lib/constants';
import type { CriterionKey, CriterionScore } from '@/types/domain';

/**
 * DecisionReceipt — §12.7. On approval, the ledger freezes into a document-like
 * artefact: registry number, the frozen score breakdown AS IT STOOD at approval
 * (never recomputed), the approving officer, a timestamp, and a faint embossed
 * crest. Paper-like on purpose — this is the artefact this organisation trusts,
 * and it makes the decision reviewable years later.
 */
export interface DecisionReceiptProps {
  registryNumber: string;
  programmeTitle: string;
  trainerName: string;
  trainerRank: string;
  forceNumber: string;
  station?: string;
  frozenScore: number;
  frozenBreakdown: CriterionScore[];
  frozenRankPosition: number;
  frozenWeights: Record<CriterionKey, number>;
  weightsWereSimulated: boolean;
  approvedByName: string;
  approvalDate: string;
  remarks?: string;
  className?: string;
}

export const DecisionReceipt = forwardRef<HTMLDivElement, DecisionReceiptProps>(
  function DecisionReceipt(props, ref) {
    const {
      registryNumber,
      programmeTitle,
      trainerName,
      trainerRank,
      forceNumber,
      station,
      frozenScore,
      frozenBreakdown,
      frozenRankPosition,
      frozenWeights,
      weightsWereSimulated,
      approvedByName,
      approvalDate,
      remarks,
      className,
    } = props;

    return (
      <div
        ref={ref}
        className={cn('relative overflow-hidden rounded-md border border-strong bg-surface p-6 shadow-e2 md:p-8', className)}
      >
        {/* Embossed crest watermark (~4%). */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-5" aria-hidden="true">
          <Crest size={320} className="text-ink" />
        </div>

        <div className="relative flex flex-col gap-6">
          {/* Header + registry number */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <Crest size={36} className="text-brand" />
              <div className="flex flex-col">
                <span className="font-mono text-label uppercase text-text-muted">Decision receipt</span>
                <span className="text-h3 text-ink">Allocation record</span>
              </div>
            </div>
            <div className="flex flex-col items-end">
              <span className="font-mono text-label uppercase text-text-muted">Registry no.</span>
              <span className="font-mono text-data-lg tabular-nums text-ink">{registryNumber}</span>
            </div>
          </div>

          <div className="receipt-rule" aria-hidden="true" />

          {/* Particulars */}
          <KeyValueList
            columns={2}
            items={[
              { label: 'Programme', value: programmeTitle },
              { label: 'Trainer', value: `${trainerRank} ${trainerName}` },
              { label: 'Force no.', value: formatForceNumber(forceNumber), mono: true },
              { label: 'Station', value: station ?? '—' },
              { label: 'Rank at approval', value: `${ordinal(frozenRankPosition)} of the ranking`, mono: true },
              { label: 'Approved by', value: approvedByName },
            ]}
          />

          {/* Frozen score */}
          <div className="flex flex-col gap-3 rounded-md border border-hairline bg-surface-sunken p-4">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-label uppercase text-text-muted">
                Suitability score at approval
              </span>
              <span className="font-mono text-data-xl tabular-nums text-ink">
                {frozenScore.toFixed(1)}
                <span className="text-data text-text-muted"> / 100</span>
              </span>
            </div>
            <ScoreLedger breakdown={frozenBreakdown} total={frozenScore} size="md" showTotal={false} interactive={false} />
            <div className="mt-1 divide-y divide-hairline">
              {frozenBreakdown.map((c) => (
                <CriterionRow key={c.key} criterion={c} />
              ))}
            </div>
          </div>

          {/* Weights in force */}
          <div className="flex flex-col gap-2">
            <span className="font-mono text-label uppercase text-text-muted">
              Weighting in force {weightsWereSimulated && '· simulated at approval'}
            </span>
            <div className="flex flex-wrap gap-2">
              {frozenBreakdown.map((c) => (
                <span key={c.key} className="inline-flex items-center gap-1.5 rounded-sm bg-surface-sunken px-2 py-1 font-mono text-label text-text-secondary">
                  {CRITERION_META[c.key].shortLabel}
                  <span className="tabular-nums text-ink">{frozenWeights[c.key]}</span>
                </span>
              ))}
            </div>
          </div>

          {remarks && (
            <div className="flex flex-col gap-1">
              <span className="font-mono text-label uppercase text-text-muted">Remarks</span>
              <p className="text-body text-text-secondary">{remarks}</p>
            </div>
          )}

          <div className="receipt-rule" aria-hidden="true" />

          <div className="flex items-center justify-between">
            <span className="text-body-sm text-text-muted">
              Approved {formatTimestamp(approvalDate)}
            </span>
            <span className="font-mono text-label uppercase text-text-muted">Uganda Police Force</span>
          </div>
        </div>
      </div>
    );
  },
);
