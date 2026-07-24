import { client } from '../axiosClient';
import type {
  Paginated,
  TrainerCredentialsInput,
  TrainerEvaluationsResponse,
  TrainerFilters,
  TrainerSelfUpdateInput,
} from '@/types/api';
import type { Trainer } from '@/types/domain';

export const listTrainers = (filters: TrainerFilters = {}): Promise<Paginated<Trainer>> =>
  client.get('/trainers', { params: filters }).then((r) => r.data);

export const getTrainer = (trainerId: number): Promise<Trainer> =>
  client.get(`/trainers/${trainerId}`).then((r) => r.data);

export const getTrainerEvaluations = (trainerId: number): Promise<TrainerEvaluationsResponse> =>
  client.get(`/trainers/${trainerId}/evaluations`).then((r) => r.data);

/** The trainer record linked to a user account (Trainer self-service, FR-02). */
export const getMyTrainer = (userId: number): Promise<Trainer> =>
  client.get('/me/trainer', { params: { userId } }).then((r) => r.data);

export const updateTrainer = (trainerId: number, body: TrainerSelfUpdateInput): Promise<Trainer> =>
  client.patch(`/trainers/${trainerId}`, body).then((r) => r.data);

/** FR-03 — save the trainer's qualifications and specialisations. */
export const updateTrainerCredentials = (
  trainerId: number,
  body: TrainerCredentialsInput,
): Promise<Trainer> =>
  client.patch(`/trainers/${trainerId}/credentials`, body).then((r) => r.data);
