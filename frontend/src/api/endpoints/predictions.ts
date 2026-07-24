import { client } from '../axiosClient';
import type { CriterionKey, PredictionRun } from '@/types/domain';

/**
 * The service-layer signature is FINAL (§9.3) — it must not change when the real
 * Prediction Engine backend arrives.
 */
export const generatePrediction = (
  programmeId: number,
  weights?: Partial<Record<CriterionKey, number>>,
): Promise<PredictionRun> =>
  client.post(`/programmes/${programmeId}/predict`, { weights }).then((r) => r.data);

export const getPrediction = (programmeId: number): Promise<PredictionRun> =>
  client.get(`/programmes/${programmeId}/prediction`).then((r) => r.data);
