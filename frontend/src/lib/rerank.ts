/**
 * Client-side re-rank for the Weight Studio (§12.6). Changing weights never
 * changes a criterion's normalised value, so re-ranking is a pure recompute over
 * the existing breakdown — no server round-trip, no re-score. Deterministic
 * tie-break mirrors the engine (score → performance → years → load → force no.).
 */
import type { CriterionKey, Prediction, Trainer } from '@/types/domain';
import { recomputeWithWeights } from '@/lib/scoring';

export interface RerankResult {
  ranked: Prediction[];
  deltaByTrainer: Record<number, number>; // policyRank − newRank (positive = moved up)
  changedCount: number;
  topFromTrainerId: number | null;
  topToTrainerId: number | null;
}

export function rerank(
  basePredictions: Prediction[],
  weights: Record<CriterionKey, number>,
  trainerMap: Map<number, Trainer>,
): RerankResult {
  const policyRank = new Map(basePredictions.map((p) => [p.trainerId, p.rankPosition]));
  const topFromTrainerId = basePredictions[0]?.trainerId ?? null;

  const rescored = basePredictions.map((p) => {
    const { breakdown, total } = recomputeWithWeights(p.breakdown, weights);
    return { ...p, breakdown, predictionScore: total };
  });

  rescored.sort((a, b) => {
    if (b.predictionScore !== a.predictionScore) return b.predictionScore - a.predictionScore;
    const perfA = a.breakdown.find((c) => c.key === 'PERFORMANCE')?.normalized ?? 0;
    const perfB = b.breakdown.find((c) => c.key === 'PERFORMANCE')?.normalized ?? 0;
    if (perfB !== perfA) return perfB - perfA;
    const ta = trainerMap.get(a.trainerId);
    const tb = trainerMap.get(b.trainerId);
    if (ta && tb) {
      if (tb.yearsExperience !== ta.yearsExperience) return tb.yearsExperience - ta.yearsExperience;
      if (ta.currentAllocations !== tb.currentAllocations)
        return ta.currentAllocations - tb.currentAllocations;
      return Number(ta.forceNumber) - Number(tb.forceNumber);
    }
    return 0;
  });

  const deltaByTrainer: Record<number, number> = {};
  let changedCount = 0;
  rescored.forEach((p, i) => {
    const newRank = i + 1;
    p.rankPosition = newRank;
    const old = policyRank.get(p.trainerId) ?? newRank;
    deltaByTrainer[p.trainerId] = old - newRank;
    if (old !== newRank) changedCount += 1;
  });

  return {
    ranked: rescored,
    deltaByTrainer,
    changedCount,
    topFromTrainerId,
    topToTrainerId: rescored[0]?.trainerId ?? null,
  };
}
