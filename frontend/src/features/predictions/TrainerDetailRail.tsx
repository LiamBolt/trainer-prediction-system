import { Check, SkipForward, GraduationCap, Award, History } from 'lucide-react';
import {
  Avatar,
  Badge,
  Button,
  Separator,
} from '@/components/ui';
import {
  ScoreLedger,
  CriterionRow,
  RationaleCard,
  ConfidenceMeter,
  CounterfactualNote,
  AvailabilityPill,
} from '@/components/prediction';
import { PROFICIENCY_LABELS, QUALIFICATION_LABELS } from '@/lib/constants';
import { formatDate, formatForceNumber, formatRating } from '@/lib/format';
import type { Prediction, Trainer } from '@/types/domain';

/**
 * The prediction detail rail (§11.4). Everything an Administrator needs to defend
 * the choice: rationale, the full ledger with per-criterion rows, honest
 * confidence, the counterfactual, qualifications, specialisations, recent
 * evaluations, and the Approve / Skip actions.
 */
export function TrainerDetailRail({
  prediction,
  trainer,
  isAdmin,
  onApprove,
  onSkip,
  canSkip,
}: {
  prediction: Prediction;
  trainer: Trainer;
  isAdmin: boolean;
  onApprove: () => void;
  onSkip: () => void;
  canSkip: boolean;
}) {
  const recentEvals = [...trainer.performanceHistory]
    .sort((a, b) => new Date(b.evaluationDate).getTime() - new Date(a.evaluationDate).getTime())
    .slice(0, 3);

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Avatar name={trainer.fullName} size={40} />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-h3 text-ink">
            {trainer.policeRank} {trainer.fullName}
          </span>
          <span className="truncate font-mono text-label text-text-muted">
            {formatForceNumber(trainer.forceNumber)} · {trainer.station}
          </span>
        </div>
        <AvailabilityPill status={trainer.availabilityStatus} />
      </div>

      <RationaleCard rationale={prediction.rationale} />

      {/* Ledger + criterion rows */}
      <div className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <span className="font-mono text-label uppercase text-text-muted">Score ledger</span>
          <span className="font-mono text-data-xl tabular-nums text-ink">
            {prediction.predictionScore.toFixed(1)}
            <span className="text-data text-text-muted"> / 100</span>
          </span>
        </div>
        <ScoreLedger breakdown={prediction.breakdown} total={prediction.predictionScore} size="md" showTotal={false} />
        <div className="divide-y divide-hairline">
          {prediction.breakdown.map((c) => (
            <CriterionRow key={c.key} criterion={c} />
          ))}
        </div>
      </div>

      {/* Confidence (with honest low note) + counterfactual */}
      <div className="flex flex-col gap-3">
        <ConfidenceMeter band={prediction.confidenceBand} showNote />
        <CounterfactualNote counterfactual={prediction.counterfactual} />
      </div>

      <Separator />

      {/* Specialisations */}
      <Section icon={<Award size={16} className="shrink-0" />} title="Specialisations">
        <div className="flex flex-wrap gap-2">
          {trainer.specializations.map((s) => (
            <Badge key={s.specializationId} tone="neutral" dot={false}>
              {s.specializationArea} · {PROFICIENCY_LABELS[s.proficiencyLevel]}
            </Badge>
          ))}
        </div>
      </Section>

      {/* Qualifications */}
      <Section icon={<GraduationCap size={16} className="shrink-0" />} title="Qualifications">
        <ul className="flex flex-col gap-2">
          {trainer.qualifications.map((q) => (
            <li key={q.qualificationId} className="flex items-baseline justify-between gap-2">
              <span className="text-body-sm text-ink">
                {QUALIFICATION_LABELS[q.qualificationLevel]} — {q.institutionName}
              </span>
              <span className="shrink-0 font-mono text-label tabular-nums text-text-muted">
                {q.yearObtained}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      {/* Recent evaluations */}
      <Section icon={<History size={16} className="shrink-0" />} title="Recent evaluations">
        {recentEvals.length === 0 ? (
          <p className="text-body-sm text-text-muted">No evaluations recorded yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {recentEvals.map((e) => (
              <li key={e.evaluationId} className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 truncate text-body-sm text-text-secondary">{e.programmeTitle}</span>
                <span className="shrink-0 font-mono text-data tabular-nums text-ink">
                  {formatRating(e.scoreAwarded)}
                  <span className="text-text-disabled"> / 5</span>
                  <span className="ml-2 text-label text-text-muted">{formatDate(e.evaluationDate)}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* Actions (Administrator only) */}
      {isAdmin && (
        <div className="sticky bottom-0 flex gap-3 border-t border-hairline bg-surface pt-4">
          <Button className="flex-1" onClick={onApprove} icon={<Check size={16} className="shrink-0" />}>
            Approve this trainer
          </Button>
          <Button variant="secondary" onClick={onSkip} disabled={!canSkip} icon={<SkipForward size={16} className="shrink-0" />}>
            Skip to next
          </Button>
        </div>
      )}
    </div>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="flex items-center gap-2 font-mono text-label uppercase text-text-muted">
        {icon}
        {title}
      </span>
      {children}
    </div>
  );
}
