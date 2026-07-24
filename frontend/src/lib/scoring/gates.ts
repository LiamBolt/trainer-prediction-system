/**
 * Stage 1 — hard gates (§7.1). Elimination, not scoring. Applied in this exact
 * order; the FIRST failing rule is the recorded reason. Excluded trainers never
 * appear in the ranked list (BR-03) but are always inspectable in the Exclusion
 * Ledger (§12.4).
 */
import type {
  ExclusionReason,
  ExcludedTrainer,
  Trainer,
  TrainingProgramme,
} from '@/types/domain';
import { QUALIFICATION_LABELS, QUALIFICATION_ORDER } from '@/lib/constants';
import { formatDateRange } from '@/lib/format';
import { highestQualification } from './criteria';

const BUSINESS_RULE: Record<ExclusionReason, 'BR-03' | 'BR-04' | 'FR-05'> = {
  UNAVAILABLE: 'BR-03',
  MISSING_SPECIALIZATION: 'BR-04',
  SCHEDULE_CONFLICT: 'BR-03',
  BELOW_MINIMUM_EXPERIENCE: 'FR-05',
  BELOW_MINIMUM_QUALIFICATION: 'FR-05',
};

export interface GateContext {
  /** A CONFIRMED allocation overlapping the programme dates, if any. */
  conflict?: { title: string; startDate: string; endDate: string } | null;
}

export interface GateOutcome {
  reason: ExclusionReason;
  reasonDetail: string;
}

/** Returns the exclusion outcome, or null if the trainer passes every gate. */
export function evaluateGates(
  trainer: Trainer,
  programme: TrainingProgramme,
  ctx: GateContext = {},
): GateOutcome | null {
  // 1 — availability (BR-03)
  if (trainer.availabilityStatus === 'UNAVAILABLE') {
    return { reason: 'UNAVAILABLE', reasonDetail: 'Marked unavailable for assignment.' };
  }

  // 2 — required specialisation (BR-04)
  const hasSpec = trainer.specializations.some(
    (s) => s.specializationArea === programme.requiredSpecialization,
  );
  if (!hasSpec) {
    return {
      reason: 'MISSING_SPECIALIZATION',
      reasonDetail: `Does not hold the required specialisation (${programme.requiredSpecialization}).`,
    };
  }

  // 3 — schedule conflict with a CONFIRMED allocation
  if (ctx.conflict) {
    return {
      reason: 'SCHEDULE_CONFLICT',
      reasonDetail: `Assigned to ${ctx.conflict.title} · ${formatDateRange(
        ctx.conflict.startDate,
        ctx.conflict.endDate,
      )}.`,
    };
  }

  // 4 — minimum experience (FR-05)
  if (trainer.yearsExperience < programme.minimumExperience) {
    return {
      reason: 'BELOW_MINIMUM_EXPERIENCE',
      reasonDetail: `${trainer.yearsExperience} years of service; ${programme.minimumExperience} required.`,
    };
  }

  // 5 — minimum qualification when set (FR-05)
  if (programme.minimumQualification) {
    const highest = highestQualification(trainer);
    const highestIdx = highest ? QUALIFICATION_ORDER.indexOf(highest.qualificationLevel) : -1;
    const requiredIdx = QUALIFICATION_ORDER.indexOf(programme.minimumQualification);
    if (highestIdx < requiredIdx) {
      const held = highest
        ? QUALIFICATION_LABELS[highest.qualificationLevel]
        : 'no formal qualification';
      return {
        reason: 'BELOW_MINIMUM_QUALIFICATION',
        reasonDetail: `Highest qualification is ${held.toLowerCase()}; ${QUALIFICATION_LABELS[
          programme.minimumQualification
        ].toLowerCase()} required.`,
      };
    }
  }

  return null;
}

export function toExcludedTrainer(trainer: Trainer, outcome: GateOutcome): ExcludedTrainer {
  return {
    trainerId: trainer.trainerId,
    fullName: trainer.fullName,
    policeRank: trainer.policeRank,
    forceNumber: trainer.forceNumber,
    reason: outcome.reason,
    reasonDetail: outcome.reasonDetail,
    businessRule: BUSINESS_RULE[outcome.reason],
  };
}
