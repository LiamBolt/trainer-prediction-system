import { client } from '../axiosClient';
import { toPaginated } from '../normalize';
import type {
  AllocationFilters,
  AllocationListItem,
  ApproveAllocationInput,
  DeclineAssignmentInput,
  Paginated,
} from '@/types/api';
import type { Allocation } from '@/types/domain';

export const listAllocations = (
  filters: AllocationFilters = {},
): Promise<Paginated<AllocationListItem>> =>
  client.get('/allocations', { params: filters }).then((r) => toPaginated<AllocationListItem>(r.data));

export const getAllocation = (allocationId: number): Promise<AllocationListItem> =>
  client.get(`/allocations/${allocationId}`).then((r) => r.data);

/**
 * FR-09 — the signed-in trainer's own assignments, grouped server-side and scoped by
 * the bearer token. A trainer must use THIS (not GET /allocations, which is
 * Admin/Officer-only and 403s for a trainer).
 */
export const getMyAssignments = (): Promise<{
  pending: AllocationListItem[];
  upcoming: AllocationListItem[];
  past: AllocationListItem[];
}> => client.get('/trainers/me/assignments').then((r) => r.data);

/** FR-08 — the explicit Administrator approval. */
export const approveAllocation = (body: ApproveAllocationInput): Promise<Allocation> =>
  client.post('/allocations', body).then((r) => r.data);

/** FR-09 — trainer declines with a required reason. */
export const declineAssignment = (body: DeclineAssignmentInput): Promise<Allocation> =>
  client.post(`/allocations/${body.allocationId}/decline`, body).then((r) => r.data);

export const acceptAssignment = (allocationId: number): Promise<Allocation> =>
  client.post(`/allocations/${allocationId}/accept`).then((r) => r.data);

/** FR-08 — reuse the same ranking to promote the next candidate; no re-run. */
export const promoteNext = (allocationId: number): Promise<Allocation> =>
  client.post(`/allocations/${allocationId}/promote-next`).then((r) => r.data);
