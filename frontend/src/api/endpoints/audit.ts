import { client } from '../axiosClient';
import { toPaginated } from '../normalize';
import type { AuditFilters, Paginated } from '@/types/api';
import type { AuditLogEntry } from '@/types/domain';

/**
 * FR-13 — the audit trail. The API row uses `actorName` / `actorRole` / `action` /
 * `createdAt` / `entityType`+`entityId`; the UI's AuditLogEntry uses `userName` /
 * `userRole` / `actionPerformed` / `timestamp` / `affectedRecord`. Map here so the
 * (virtualised) table renders the real data instead of dereferencing absent fields.
 */
export const listAudit = (filters: AuditFilters = {}): Promise<Paginated<AuditLogEntry>> =>
  client.get('/audit', { params: filters }).then((r) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    toPaginated<AuditLogEntry>(r.data, (a: any) => ({
      logId: a.logId,
      userId: a.actorUserId ?? 0,
      userName: a.actorName ?? 'System',
      userRole: a.actorRole,
      actionPerformed: a.action,
      timestamp: a.createdAt,
      affectedRecord: a.entityType ? `${a.entityType}#${a.entityId ?? ''}` : '',
      detail: a.detail ?? '',
      ipAddress: a.ipAddress ?? '',
    })),
  );
