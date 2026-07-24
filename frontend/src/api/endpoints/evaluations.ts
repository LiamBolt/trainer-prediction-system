import { client } from '../axiosClient';
import type { AllocationListItem, EvaluationInput } from '@/types/api';
import type { PerformanceEvaluation } from '@/types/domain';

export interface EvaluationsResponse {
  awaiting: AllocationListItem[];
  recorded: PerformanceEvaluation[];
}

export const listEvaluations = (): Promise<EvaluationsResponse> =>
  client.get('/evaluations').then((r) => r.data);

/** FR-10 — record a performance evaluation once training is CONDUCTED. */
export const recordEvaluation = (body: EvaluationInput): Promise<PerformanceEvaluation> =>
  client.post('/evaluations', body).then((r) => r.data);
