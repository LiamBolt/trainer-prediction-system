import { describe, expect, it } from 'vitest';
import { generateDb } from '@/mocks/data/generate';
import { DEFAULT_WEIGHTS, WEIGHT_PRESETS } from '@/lib/constants';
import { rerank } from './rerank';
import type { Trainer } from '@/types/domain';

const db = generateDb();
const run = db.runs.find((r) => r.programmeId === db.featuredProgrammeId)!;
const trainerMap = new Map<number, Trainer>(db.trainers.map((t) => [t.trainerId, t]));

describe('rerank (Weight Studio, §12.6)', () => {
  it('leaves the order unchanged at policy weights', () => {
    const result = rerank(run.predictions, DEFAULT_WEIGHTS, trainerMap);
    expect(result.changedCount).toBe(0);
    expect(result.ranked[0]?.trainerId).toBe(1);
    expect(Object.values(result.deltaByTrainer).every((d) => d === 0)).toBe(true);
  });

  it('flips the top two under the performance-priority preset', () => {
    const preset = WEIGHT_PRESETS.find((p) => p.id === 'performance')!;
    const result = rerank(run.predictions, preset.weights, trainerMap);
    expect(result.topFromTrainerId).toBe(1); // IP Mugisha
    expect(result.topToTrainerId).toBe(2); // ASP Nabirye overtakes on proven performance
    expect(result.changedCount).toBeGreaterThan(0);
    expect(result.deltaByTrainer[2]).toBeGreaterThan(0); // Nabirye moved up
  });

  it('keeps every trainer in the ranking (no drops)', () => {
    const result = rerank(run.predictions, WEIGHT_PRESETS[2]!.weights, trainerMap);
    expect(result.ranked).toHaveLength(run.predictions.length);
    const ranks = result.ranked.map((p) => p.rankPosition).sort((a, b) => a - b);
    expect(ranks[0]).toBe(1);
    expect(ranks[ranks.length - 1]).toBe(run.predictions.length);
  });
});
