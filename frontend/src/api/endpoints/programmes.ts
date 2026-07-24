import { client } from '../axiosClient';
import type {
  EligibilityPreview,
  Paginated,
  ProgrammeCreateInput,
  ProgrammeDetail,
  ProgrammeFilters,
  RequirementsInput,
} from '@/types/api';
import type { TrainingProgramme } from '@/types/domain';

export const listProgrammes = (filters: ProgrammeFilters = {}): Promise<Paginated<TrainingProgramme>> =>
  client.get('/programmes', { params: filters }).then((r) => r.data);

export const createProgramme = (body: ProgrammeCreateInput): Promise<TrainingProgramme> =>
  client.post('/programmes', body).then((r) => r.data);

export const getProgramme = (programmeId: number): Promise<ProgrammeDetail> =>
  client.get(`/programmes/${programmeId}`).then((r) => r.data);

export const setRequirements = (
  programmeId: number,
  body: RequirementsInput,
): Promise<TrainingProgramme> =>
  client.post(`/programmes/${programmeId}/requirements`, body).then((r) => r.data);

/** Live eligibility preview as the Officer types requirements (FR-05). */
export const getEligibility = (
  programmeId: number,
  requirements: { specialization: string; minExp: number; minQual: string | null },
): Promise<EligibilityPreview> =>
  client
    .get(`/programmes/${programmeId}/eligibility`, {
      params: {
        specialization: requirements.specialization,
        minExp: requirements.minExp,
        minQual: requirements.minQual ?? '',
      },
    })
    .then((r) => r.data);
