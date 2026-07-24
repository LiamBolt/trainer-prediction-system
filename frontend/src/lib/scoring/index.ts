/**
 * The Prediction Engine — the frontend's transparent, deterministic stand-in for
 * the backend engine (§7). Runs the four stages end-to-end and returns a fully
 * shaped PredictionRun. When the real engine arrives, the same shapes come over
 * the wire and this module survives as the weight-simulation sandbox.
 */
import type {
  CriterionKey,
  ExcludedTrainer,
  PerformanceEvaluation,
  Prediction,
  PredictionRun,
  Trainer,
  TrainingProgramme,
} from '@/types/domain';
import { DEFAULT_WEIGHTS } from '@/lib/constants';
import { evaluateGates, toExcludedTrainer } from './gates';
import { compareCandidates, scoreCandidate, type ScoredCandidate } from './score';
import { buildCounterfactual, buildRationale } from './narrative';

export * from './gates';
export * from './criteria';
export * from './score';
export * from './narrative';

export interface RunPredictionInput {
  programme: TrainingProgramme;
  trainers: Trainer[];
  weights?: Record<CriterionKey, number>;
  /** Whether an evaluation counts toward the required specialisation. */
  isRelevantEvaluation?: (ev: PerformanceEvaluation) => boolean;
  /** Returns an overlapping CONFIRMED allocation for a trainer, if any. */
  resolveConflict?: (
    trainer: Trainer,
  ) => { title: string; startDate: string; endDate: string } | null;
  now?: Date;
  generatedDate?: string;
  elapsedMs?: number;
  weightsArePolicyDefault?: boolean;
  runId?: string;
}

function weightsAreDefault(weights: Record<CriterionKey, number>): boolean {
  return (Object.keys(DEFAULT_WEIGHTS) as CriterionKey[]).every(
    (k) => weights[k] === DEFAULT_WEIGHTS[k],
  );
}

export function runPrediction(input: RunPredictionInput): PredictionRun {
  const {
    programme,
    trainers,
    weights = DEFAULT_WEIGHTS,
    isRelevantEvaluation,
    resolveConflict,
    now,
    generatedDate = (now ?? new Date()).toISOString(),
    weightsArePolicyDefault = weightsAreDefault(weights),
  } = input;

  const excluded: ExcludedTrainer[] = [];
  const scored: ScoredCandidate[] = [];

  for (const trainer of trainers) {
    const conflict = resolveConflict?.(trainer) ?? null;
    const gate = evaluateGates(trainer, programme, { conflict });
    if (gate) {
      excluded.push(toExcludedTrainer(trainer, gate));
      continue;
    }
    scored.push(
      scoreCandidate(trainer, programme, weights, { isRelevantEvaluation, hasScheduleConflict: false, now }),
    );
  }

  // BR-05 — always highest suitability score -> lowest, deterministic tie-break.
  scored.sort(compareCandidates);
  const topTotal = scored[0]?.total ?? 0;

  const predictions: Prediction[] = scored.map((candidate, i) => {
    const rankPosition = i + 1;
    const counterfactual =
      rankPosition >= 2 && rankPosition <= 5
        ? buildCounterfactual(candidate, topTotal, weights)
        : null;
    return {
      predictionId: programme.programmeId * 100000 + candidate.trainer.trainerId,
      programmeId: programme.programmeId,
      trainerId: candidate.trainer.trainerId,
      predictionScore: candidate.total,
      confidenceLevel: candidate.confidenceLevel,
      confidenceBand: candidate.confidenceBand,
      rankPosition,
      breakdown: candidate.breakdown,
      rationale: buildRationale(candidate, programme),
      counterfactual,
      generatedDate,
    };
  });

  return {
    runId: input.runId ?? `RUN-${programme.programmeId}-${generatedDate}`,
    programmeId: programme.programmeId,
    generatedDate,
    candidatePoolSize: trainers.length,
    excludedCount: excluded.length,
    rankedCount: predictions.length,
    elapsedMs: input.elapsedMs ?? 0,
    weights,
    weightsArePolicyDefault,
    predictions,
    excluded,
  };
}
