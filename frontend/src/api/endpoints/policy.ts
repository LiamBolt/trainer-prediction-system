import { client } from '../axiosClient';
import type { WeightPolicyRecord } from '@/mocks/data';
import type { CriterionKey } from '@/types/domain';

/**
 * The API returns the active policy as `{ policyId, version, name, effectiveFrom,
 * createdByName, weights }`, where `weights` is a LIST of
 * `{ criterionKey, weight, … }`. The UI's WeightPolicyRecord expects a
 * `Record<CriterionKey, number>` plus `changedBy` / `changedAt` / `history`. Map here
 * so the Scoring Policy page loads instead of calling `.map()` on absent fields.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toPolicyRecord(raw: any): WeightPolicyRecord {
  const list: Array<{ criterionKey: CriterionKey; weight: number }> = Array.isArray(raw?.weights)
    ? raw.weights
    : [];
  const weights = Object.fromEntries(
    list.map((w) => [w.criterionKey, Number(w.weight)]),
  ) as WeightPolicyRecord['weights'];
  return {
    weights,
    changedBy: raw?.createdByName ?? '—',
    // The endpoint returns the creator's name but not their rank; the page does not
    // render the rank, so a valid placeholder keeps the type honest.
    changedByRank: (raw?.createdByRank ?? 'SP') as WeightPolicyRecord['changedByRank'],
    changedAt: raw?.effectiveFrom ?? raw?.createdAt ?? new Date().toISOString(),
    // The active-policy endpoint does not carry version history; the audit log does.
    history: [],
  };
}

/** NFR-10 — the saved scoring-policy weights. */
export const getScoringPolicy = (): Promise<WeightPolicyRecord> =>
  client.get('/scoring-policy').then((r) => toPolicyRecord(r.data));

export const saveScoringPolicy = (
  weights: Record<CriterionKey, number>,
): Promise<WeightPolicyRecord> =>
  client.post('/scoring-policy', { weights }).then((r) => toPolicyRecord(r.data));
