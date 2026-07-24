import { client } from '../axiosClient';
import type { AuditFilters, Paginated } from '@/types/api';
import type { AuditLogEntry } from '@/types/domain';

export const listAudit = (filters: AuditFilters = {}): Promise<Paginated<AuditLogEntry>> =>
  client.get('/audit', { params: filters }).then((r) => r.data);
