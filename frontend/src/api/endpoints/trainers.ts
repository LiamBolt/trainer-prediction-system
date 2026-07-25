import { client } from '../axiosClient';
import { toPaginated } from '../normalize';
import type {
  Paginated,
  TrainerCredentialsInput,
  TrainerEvaluationsResponse,
  TrainerFilters,
  TrainerSelfUpdateInput,
} from '@/types/api';
import type { Trainer } from '@/types/domain';

// The list endpoint returns a lightweight row (no qualifications / specialisations /
// history) — those load on the detail page. Default the arrays so directory rendering
// never dereferences an absent collection.
export const listTrainers = (filters: TrainerFilters = {}): Promise<Paginated<Trainer>> =>
  client.get('/trainers', { params: filters }).then((r) =>
    toPaginated<Trainer>(r.data, (t) => ({
      qualifications: [],
      specializations: [],
      performanceHistory: [],
      currentAllocations: 0,
      lastAssignedDate: null,
      ...t,
    })),
  );

export const getTrainer = (trainerId: number): Promise<Trainer> =>
  client.get(`/trainers/${trainerId}`).then((r) => r.data);

export const getTrainerEvaluations = (trainerId: number): Promise<TrainerEvaluationsResponse> =>
  client.get(`/trainers/${trainerId}/evaluations`).then((r) => r.data);

/**
 * Trainer self-service (FR-02). Identity comes from the BEARER TOKEN — there is no
 * userId parameter. The old `/me/trainer?userId=` path 404s; the real route is
 * `/trainers/me`, which returns the full TrainerDetail (profile, qualifications,
 * specialisations, and performance history).
 */
export const getMyTrainer = (): Promise<Trainer> =>
  client.get('/trainers/me').then((r) => r.data);

/** FR-02 — update your own profile (rank, station, years, contact, availability). */
export const updateMyProfile = (body: TrainerSelfUpdateInput): Promise<Trainer> =>
  client.patch('/trainers/me', body).then((r) => r.data);

export const updateTrainer = (trainerId: number, body: TrainerSelfUpdateInput): Promise<Trainer> =>
  client.patch(`/trainers/${trainerId}`, body).then((r) => r.data);

/** FR-03 — save the trainer's qualifications and specialisations. */
export const updateTrainerCredentials = (
  trainerId: number,
  body: TrainerCredentialsInput,
): Promise<Trainer> =>
  client.patch(`/trainers/${trainerId}/credentials`, body).then((r) => r.data);
