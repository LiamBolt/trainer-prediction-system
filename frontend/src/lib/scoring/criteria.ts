/**
 * Stage 2 — criterion scoring (§7.1). Each function normalises one criterion to
 * 0–100 and returns the raw value, a plain-English explanation, and a data-quality
 * flag. Pure, zero React, fully unit-testable. Weights are applied in score.ts.
 */
import type {
  CriterionKey,
  DataQuality,
  PerformanceEvaluation,
  Trainer,
  TrainingProgramme,
} from '@/types/domain';
import {
  PROFICIENCY_LABELS,
  PROFICIENCY_SCORE,
  QUALIFICATION_LABELS,
  QUALIFICATION_ORDER,
  QUALIFICATION_SCORE,
  POLICE_INSTITUTIONS,
  SPECIALIZATION_CATEGORY,
} from '@/lib/constants';

export interface CriterionResult {
  normalized: number; // 0-100
  rawValue: string;
  explanation: string;
  dataQuality: DataQuality;
}

export interface ScoringContext {
  /** True when an evaluation counts toward the required specialisation. */
  isRelevantEvaluation?: (ev: PerformanceEvaluation) => boolean;
  /** Precomputed overlap with an existing CONFIRMED allocation. */
  hasScheduleConflict?: boolean;
  /** Reference "now" for recency; defaults to system time. */
  now?: Date;
}

// Clamp to 0–100 and round to 2 decimals so normalisation is float-noise free.
const clamp = (n: number, lo = 0, hi = 100) =>
  Math.round(Math.max(lo, Math.min(hi, n)) * 100) / 100;

/** Highest qualification the trainer holds, by the canonical ordering. */
export function highestQualification(trainer: Trainer) {
  return [...trainer.qualifications].sort(
    (a, b) =>
      QUALIFICATION_ORDER.indexOf(b.qualificationLevel) -
      QUALIFICATION_ORDER.indexOf(a.qualificationLevel),
  )[0];
}

// --- SPECIALIZATION (30) --------------------------------------------------

export function scoreSpecialization(
  trainer: Trainer,
  programme: TrainingProgramme,
): CriterionResult {
  const match = trainer.specializations.find(
    (s) => s.specializationArea === programme.requiredSpecialization,
  );
  if (!match) {
    // Should be gated out at BR-04; defensive fallback.
    return {
      normalized: 0,
      rawValue: 'No matching specialisation',
      explanation: `Holds no specialisation in ${programme.requiredSpecialization}.`,
      dataQuality: 'MISSING',
    };
  }
  const base = PROFICIENCY_SCORE[match.proficiencyLevel];
  const hasBreadth = trainer.specializations.some(
    (s) =>
      s.specializationArea !== programme.requiredSpecialization &&
      SPECIALIZATION_CATEGORY[s.specializationArea] === programme.category,
  );
  const bonus = hasBreadth ? 10 : 0;
  const normalized = clamp(base + bonus);
  const breadthNote = hasBreadth
    ? ` A second specialisation also fits the ${programme.category} category.`
    : '';
  return {
    normalized,
    rawValue: `${PROFICIENCY_LABELS[match.proficiencyLevel]} · ${programme.requiredSpecialization}`,
    explanation: `Holds ${PROFICIENCY_LABELS[match.proficiencyLevel]} proficiency in ${programme.requiredSpecialization}.${breadthNote}`,
    dataQuality: 'COMPLETE',
  };
}

// --- PERFORMANCE (25) -----------------------------------------------------

export interface PerformanceDetail extends CriterionResult {
  mean: number | null;
  evaluationCount: number;
  usedRelevant: boolean;
}

export function scorePerformance(
  trainer: Trainer,
  programme: TrainingProgramme,
  ctx: ScoringContext = {},
): PerformanceDetail {
  const all = trainer.performanceHistory;
  const relevant = ctx.isRelevantEvaluation ? all.filter(ctx.isRelevantEvaluation) : [];
  const usedRelevant = relevant.length >= 2;
  const used = usedRelevant ? relevant : all;

  if (used.length === 0) {
    // Neutral prior — never punish a trainer for a system with no history (§7.1).
    return {
      normalized: 55,
      rawValue: 'No evaluations recorded',
      explanation:
        'No past evaluations exist yet, so a neutral score was used rather than a zero.',
      dataQuality: 'MISSING',
      mean: null,
      evaluationCount: 0,
      usedRelevant: false,
    };
  }

  const mean = used.reduce((s, e) => s + e.scoreAwarded, 0) / used.length;
  const normalized = clamp(((mean - 1) / 4) * 100);
  const dataQuality: DataQuality = usedRelevant ? 'COMPLETE' : 'PARTIAL';
  const scope = usedRelevant
    ? `${programme.category.toLowerCase()} courses`
    : 'all recorded courses';
  return {
    normalized,
    rawValue: `${mean.toFixed(1)} of 5 · ${used.length} evaluation${used.length === 1 ? '' : 's'}`,
    explanation: `Averaged ${mean.toFixed(1)} out of 5 across ${used.length} ${scope}.`,
    dataQuality,
    mean,
    evaluationCount: used.length,
    usedRelevant,
  };
}

// --- EXPERIENCE (20) ------------------------------------------------------

export function scoreExperience(trainer: Trainer): CriterionResult {
  const normalized = clamp(Math.min(trainer.yearsExperience / 20, 1) * 100);
  return {
    normalized,
    rawValue: `${trainer.yearsExperience} years`,
    explanation: `Has ${trainer.yearsExperience} years of service (20 years is the ceiling).`,
    dataQuality: 'COMPLETE',
  };
}

// --- QUALIFICATION (15) ---------------------------------------------------

export function scoreQualification(trainer: Trainer): CriterionResult {
  const highest = highestQualification(trainer);
  if (!highest) {
    return {
      normalized: 0,
      rawValue: 'None recorded',
      explanation: 'No formal qualification is on record.',
      dataQuality: 'MISSING',
    };
  }
  const base = QUALIFICATION_SCORE[highest.qualificationLevel];
  const fromPoliceCollege = trainer.qualifications.some((q) =>
    POLICE_INSTITUTIONS.has(q.institutionName),
  );
  const bonus = fromPoliceCollege ? 8 : 0;
  const normalized = clamp(base + bonus);
  const collegeNote = fromPoliceCollege ? ' from a police training institution' : '';
  return {
    normalized,
    rawValue: `${QUALIFICATION_LABELS[highest.qualificationLevel]} · ${highest.institutionName}`,
    explanation: `Highest qualification is a ${QUALIFICATION_LABELS[highest.qualificationLevel].toLowerCase()}${collegeNote}.`,
    dataQuality: 'COMPLETE',
  };
}

// --- AVAILABILITY (10) ----------------------------------------------------

export function scoreAvailability(trainer: Trainer): CriterionResult {
  let normalized = clamp(100 - trainer.currentAllocations * 25);
  if (trainer.availabilityStatus === 'ASSIGNED') normalized = Math.min(normalized, 50);
  const load =
    trainer.currentAllocations === 0
      ? 'no current allocations'
      : `${trainer.currentAllocations} current allocation${trainer.currentAllocations === 1 ? '' : 's'}`;
  return {
    normalized,
    rawValue: `${trainer.availabilityStatus === 'ASSIGNED' ? 'Assigned' : 'Available'} · ${load}`,
    explanation: `Currently has ${load}, leaving room to take on this course.`,
    dataQuality: 'COMPLETE',
  };
}

/** Compute all five criterion results for a trainer against a programme. */
export function computeCriteria(
  trainer: Trainer,
  programme: TrainingProgramme,
  ctx: ScoringContext = {},
): Record<CriterionKey, CriterionResult> & { performance: PerformanceDetail } {
  const performance = scorePerformance(trainer, programme, ctx);
  return {
    SPECIALIZATION: scoreSpecialization(trainer, programme),
    PERFORMANCE: performance,
    EXPERIENCE: scoreExperience(trainer),
    QUALIFICATION: scoreQualification(trainer),
    AVAILABILITY: scoreAvailability(trainer),
    performance,
  };
}
