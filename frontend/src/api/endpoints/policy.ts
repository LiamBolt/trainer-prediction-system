import { client } from '../axiosClient';
import type { WeightPolicyRecord } from '@/mocks/data';
import type { CriterionKey } from '@/types/domain';

/** NFR-10 — the saved scoring-policy weights and their change history. */
export const getScoringPolicy = (): Promise<WeightPolicyRecord> =>
  client.get('/scoring-policy').then((r) => r.data);

export const saveScoringPolicy = (
  weights: Record<CriterionKey, number>,
): Promise<WeightPolicyRecord> =>
  client.post('/scoring-policy', { weights }).then((r) => r.data);
