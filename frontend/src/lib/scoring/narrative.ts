/**
 * Stage 4 — narrative generation (§7.1). The rationale is the single most
 * important piece of text in the product (§12.3). The counterfactual is only
 * ever produced when a single change genuinely closes the gap — never invented.
 */
import type { CriterionKey, TrainingProgramme } from '@/types/domain';
import { PROFICIENCY_LABELS } from '@/lib/constants';
import { surname } from '@/lib/format';
import type { ScoredCandidate } from './score';

/** One plain-English sentence naming the trainer's strongest evidence (§12.3). */
export function buildRationale(candidate: ScoredCandidate, programme: TrainingProgramme): string {
  const { trainer } = candidate;
  const name = `${trainer.policeRank} ${surname(trainer.fullName)}`;
  const match = trainer.specializations.find(
    (s) => s.specializationArea === programme.requiredSpecialization,
  );
  const prof = match ? PROFICIENCY_LABELS[match.proficiencyLevel] : 'some';
  const spec = programme.requiredSpecialization;
  const years = trainer.yearsExperience;
  const perf = candidate.results.performance;

  if (perf.mean === null) {
    return (
      `${name} holds ${prof} proficiency in ${spec} and has ${years} years of service, ` +
      `but has no recorded evaluations yet — so this ranking rests on qualifications and availability.`
    );
  }

  return (
    `${name} holds ${prof} proficiency in ${spec}, has ${years} years of service, ` +
    `and averaged ${perf.mean.toFixed(1)} out of 5 across ${perf.evaluationCount} previous ` +
    `${spec.toLowerCase()} course${perf.evaluationCount === 1 ? '' : 's'}.`
  );
}

/**
 * The smallest single change that would lift this candidate to rank 1, or null
 * when no single change closes the gap. Ranks 2–5 only. Never invents one.
 */
export function buildCounterfactual(
  candidate: ScoredCandidate,
  topTotal: number,
  weights: Record<CriterionKey, number>,
): string | null {
  const needed = Math.round((topTotal - candidate.total) * 10) / 10 + 0.05;
  if (needed <= 0) return null; // already at/above the top score (lost on tie-break only)

  // Lever 1 — one further evaluation.
  const perf = candidate.results.performance;
  const wPerf = weights.PERFORMANCE;
  if (wPerf > 0) {
    const oldNorm = candidate.breakdown.find((c) => c.key === 'PERFORMANCE')?.normalized ?? 55;
    const requiredNewNorm = oldNorm + (needed * 100) / wPerf;
    if (requiredNewNorm <= 100) {
      const requiredMean = (requiredNewNorm / 100) * 4 + 1;
      const count = perf.mean === null ? 0 : perf.evaluationCount;
      const sum = perf.mean === null ? 0 : perf.mean * perf.evaluationCount;
      const s = requiredMean * (count + 1) - sum;
      if (s <= 1) {
        return 'Would rank 1st with one further recorded evaluation.';
      }
      if (s <= 5) {
        const rounded = Math.ceil(s * 10) / 10;
        return `Would rank 1st with one further evaluation at ${rounded.toFixed(1)} or above.`;
      }
    }
  }

  // Lever 2 — additional years of service (below the 20-year ceiling).
  const wExp = weights.EXPERIENCE;
  if (wExp > 0 && candidate.trainer.yearsExperience < 20) {
    const oldExpNorm =
      candidate.breakdown.find((c) => c.key === 'EXPERIENCE')?.normalized ?? 0;
    for (let y = 1; candidate.trainer.yearsExperience + y <= 20; y++) {
      const newExpNorm = Math.min((candidate.trainer.yearsExperience + y) / 20, 1) * 100;
      const delta = (wExp * (newExpNorm - oldExpNorm)) / 100;
      if (delta >= needed) {
        return `Would rank 1st with ${y} more year${y === 1 ? '' : 's'} of service.`;
      }
    }
  }

  return null;
}
