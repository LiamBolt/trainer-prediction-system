import { client } from '../axiosClient';
import { toPaginated } from '../normalize';
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
  client.get('/programmes', { params: filters }).then((r) => toPaginated<TrainingProgramme>(r.data));

export const createProgramme = (body: ProgrammeCreateInput): Promise<TrainingProgramme> =>
  client.post('/programmes', body).then((r) => r.data);

// The API returns `{ programme, hasRun, latestRun, allocationCount, timeline }`; the
// UI's ProgrammeDetail expects `{ programme, allocation, hasRun, auditTrail }`. Map the
// names and default the collections so the detail view never dereferences an absent
// field. (`timeline` is a status-event list, a different shape from AuditLogEntry, so
// the audit trail is left empty rather than mis-rendered.)
export const getProgramme = (programmeId: number): Promise<ProgrammeDetail> =>
  client.get(`/programmes/${programmeId}`).then((r) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const d = (r.data ?? {}) as any;
    return {
      programme: d.programme,
      allocation: d.allocation ?? null,
      hasRun: d.hasRun ?? false,
      auditTrail: Array.isArray(d.auditTrail) ? d.auditTrail : [],
    };
  });

export const setRequirements = (
  programmeId: number,
  body: RequirementsInput,
): Promise<TrainingProgramme> =>
  client.post(`/programmes/${programmeId}/requirements`, body).then((r) => r.data);

/**
 * Eligibility preview (FR-05). The API computes this from the programme's SAVED
 * requirements (it ignores any query params), so this takes no criteria and is only
 * meaningful once requirements have been saved at least once.
 */
export const getEligibility = (programmeId: number): Promise<EligibilityPreview> =>
  client.get(`/programmes/${programmeId}/eligibility`).then((r) => r.data);
