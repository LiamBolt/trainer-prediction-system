/**
 * Stage 3 — total, confidence, deterministic tie-break, rank (§7.1). Also the
 * lightweight weight recompute the Weight Studio uses: changing weights never
 * changes a criterion's `normalized` value, only its `contribution` and the
 * total — so re-ranking is a pure recompute over the existing breakdown.
 */
import type {
  ConfidenceBand,
  CriterionKey,
  CriterionScore,
  Trainer,
} from '@/types/domain';
import { CRITERION_META, CRITERION_ORDER, confidenceBandFor } from '@/lib/constants';
import type { CriterionResult, PerformanceDetail, ScoringContext } from './criteria';
import { computeCriteria } from './criteria';

export const round1 = (n: number) => Math.round(n * 10) / 10;
export const round2 = (n: number) => Math.round(n * 100) / 100;

/** Build the five-criterion breakdown for a trainer, given weights. */
export function buildBreakdown(
  results: Record<CriterionKey, CriterionResult>,
  weights: Record<CriterionKey, number>,
): CriterionScore[] {
  return CRITERION_ORDER.map((key) => {
    const r = results[key];
    const weight = weights[key];
    return {
      key,
      label: CRITERION_META[key].label,
      weight,
      rawValue: r.rawValue,
      normalized: round2(r.normalized),
      contribution: round1((weight * r.normalized) / 100),
      explanation: r.explanation,
      dataQuality: r.dataQuality,
    };
  });
}

export function computeTotal(breakdown: CriterionScore[]): number {
  return round1(breakdown.reduce((s, c) => s + c.contribution, 0));
}

/** Recompute contributions + total for new weights (Weight Studio, §12.6). */
export function recomputeWithWeights(
  breakdown: CriterionScore[],
  weights: Record<CriterionKey, number>,
): { breakdown: CriterionScore[]; total: number } {
  const next = breakdown.map((c) => {
    const weight = weights[c.key];
    return { ...c, weight, contribution: round1((weight * c.normalized) / 100) };
  });
  return { breakdown: next, total: computeTotal(next) };
}

// --- Confidence (data completeness, NOT statistical confidence, §7.1) -----

const MONTH_MS = 1000 * 60 * 60 * 24 * 30.4375;

export function computeConfidence(
  trainer: Trainer,
  now: Date = new Date(),
): { level: number; band: ConfidenceBand } {
  const evals = trainer.performanceHistory;
  const evaluationDepth = Math.min(evals.length / 5, 1) * 100;

  let recencyFactor = 40;
  if (evals.length > 0) {
    const mostRecent = Math.max(...evals.map((e) => new Date(e.evaluationDate).getTime()));
    const ageMonths = Math.max(0, (now.getTime() - mostRecent) / MONTH_MS);
    // 100 up to 24 months, then linear decay to a floor of 40 by 60 months.
    if (ageMonths <= 24) recencyFactor = 100;
    else recencyFactor = Math.max(40, 100 - ((ageMonths - 24) / 36) * 60);
  }

  const level = Math.round(
    0.45 * evaluationDepth + 0.35 * trainer.profileCompleteness + 0.2 * recencyFactor,
  );
  return { level, band: confidenceBandFor(level) };
}

// --- Deterministic tie-break + ranking (§7.1) -----------------------------

export interface ScoredCandidate {
  trainer: Trainer;
  results: Record<CriterionKey, CriterionResult> & { performance: PerformanceDetail };
  breakdown: CriterionScore[];
  total: number;
  performanceMean: number | null;
  confidenceLevel: number;
  confidenceBand: ConfidenceBand;
}

/**
 * Sort comparator — never lets ranks jitter between runs. Order: score desc,
 * then performance mean desc, years desc, current allocations asc, force number asc.
 */
export function compareCandidates(a: ScoredCandidate, b: ScoredCandidate): number {
  if (b.total !== a.total) return b.total - a.total;
  const meanA = a.performanceMean ?? -1;
  const meanB = b.performanceMean ?? -1;
  if (meanB !== meanA) return meanB - meanA;
  if (b.trainer.yearsExperience !== a.trainer.yearsExperience)
    return b.trainer.yearsExperience - a.trainer.yearsExperience;
  if (a.trainer.currentAllocations !== b.trainer.currentAllocations)
    return a.trainer.currentAllocations - b.trainer.currentAllocations;
  return Number(a.trainer.forceNumber) - Number(b.trainer.forceNumber);
}

/** Score a single trainer (all stages except gating). */
export function scoreCandidate(
  trainer: Trainer,
  programme: import('@/types/domain').TrainingProgramme,
  weights: Record<CriterionKey, number>,
  ctx: ScoringContext = {},
): ScoredCandidate {
  const results = computeCriteria(trainer, programme, ctx);
  const breakdown = buildBreakdown(results, weights);
  const total = computeTotal(breakdown);
  const { level, band } = computeConfidence(trainer, ctx.now);
  return {
    trainer,
    results,
    breakdown,
    total,
    performanceMean: results.performance.mean,
    confidenceLevel: level,
    confidenceBand: band,
  };
}
