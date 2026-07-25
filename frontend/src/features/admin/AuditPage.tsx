import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Download, Lock } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { FilterBar } from '@/components/table/FilterBar';
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  ErrorState,
  Select,
  Skeleton,
  Badge,
} from '@/components/ui';
import { auditApi } from '@/api/endpoints';
import { downloadCsv } from '@/lib/csv';
import { ROLE_LABELS } from '@/lib/constants';
import { formatTimestamp } from '@/lib/format';
import type { AuditAction, RoleName } from '@/types/domain';

const ACTIONS: AuditAction[] = [
  'LOGIN_SUCCESS', 'LOGIN_FAILED', 'ACCOUNT_LOCKED', 'LOGOUT',
  'PROGRAMME_CREATED', 'REQUIREMENTS_DEFINED', 'REQUIREMENTS_CHANGED',
  'PREDICTION_GENERATED', 'WEIGHTS_SIMULATED', 'WEIGHTS_SAVED',
  'ALLOCATION_APPROVED', 'ALLOCATION_DECLINED', 'CANDIDATE_SKIPPED',
  'ASSIGNMENT_ACCEPTED', 'ASSIGNMENT_DECLINED',
  'EVALUATION_RECORDED', 'REPORT_EXPORTED',
  'USER_CREATED', 'USER_MODIFIED', 'USER_DEACTIVATED', 'ROLE_CHANGED',
  'UNAUTHORISED_ATTEMPT',
];

const humanise = (a: AuditAction) => a.toLowerCase().replace(/_/g, ' ');

/**
 * Audit log (FR-13) — virtualised, immutable. There is NO edit control, NO delete
 * control, and NO bulk action for any role. Export to CSV is permitted.
 */
export function AuditPage() {
  const [action, setAction] = useState('');
  const [role, setRole] = useState('');
  const parentRef = useRef<HTMLDivElement>(null);

  const query = useQuery({
    queryKey: ['audit', { action, role }],
    queryFn: () =>
      auditApi.listAudit({
        action: (action || undefined) as AuditAction | undefined,
        role: (role || undefined) as RoleName | undefined,
        // The API caps page size at 100; asking for more is a 422. This shows the
        // most recent 100 entries — add paging if a deeper history view is needed.
        pageSize: 100,
      }),
  });

  const rows = query.data?.items ?? [];
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 12,
  });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Administration"
        title="Audit log"
        description="Every consequential action in the system, recorded automatically with a timestamp and user."
      />

      {/* Immutability notice */}
      <div className="flex items-center gap-2 rounded-md border border-hairline bg-surface-sunken px-4 py-3">
        <Lock size={16} className="shrink-0 text-text-muted" />
        <span className="font-mono text-label uppercase text-text-muted">
          Immutable record · entries cannot be edited or deleted
        </span>
      </div>

      <FilterBar
        hasActiveFilters={Boolean(action || role)}
        onClear={() => {
          setAction('');
          setRole('');
        }}
        actions={
          <Button
            variant="secondary"
            size="sm"
            icon={<Download size={16} className="shrink-0" />}
            onClick={() =>
              downloadCsv('audit-log', rows, [
                { key: 'timestamp', header: 'Timestamp', value: (r) => formatTimestamp(r.timestamp) },
                { key: 'user', header: 'User', value: (r) => r.userName },
                { key: 'role', header: 'Role', value: (r) => ROLE_LABELS[r.userRole] },
                { key: 'action', header: 'Action', value: (r) => r.actionPerformed },
                { key: 'record', header: 'Affected Record', value: (r) => r.affectedRecord },
                { key: 'detail', header: 'Detail', value: (r) => r.detail },
                { key: 'ip', header: 'IP Address', value: (r) => r.ipAddress },
              ])
            }
          >
            Export CSV
          </Button>
        }
      >
        <div className="w-full sm:w-56">
          <Select
            value={action}
            onValueChange={(v) => setAction(v === 'all' ? '' : v)}
            options={[
              { value: 'all', label: 'All actions' },
              ...ACTIONS.map((a) => ({ value: a, label: humanise(a) })),
            ]}
            placeholder="Action"
            aria-label="Filter by action"
          />
        </div>
        <div className="w-full sm:w-52">
          <Select
            value={role}
            onValueChange={(v) => setRole(v === 'all' ? '' : v)}
            options={[
              { value: 'all', label: 'All roles' },
              ...Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label })),
            ]}
            placeholder="Role"
            aria-label="Filter by role"
          />
        </div>
      </FilterBar>

      {query.isLoading ? (
        <Skeleton className="h-96 rounded-md" />
      ) : query.isError ? (
        <Card>
          <CardBody>
            <ErrorState onRetry={() => query.refetch()} />
          </CardBody>
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <CardBody>
            <EmptyState title="No audit entries match these filters" description="Try clearing the filters." />
          </CardBody>
        </Card>
      ) : (
        <div className="overflow-hidden rounded-md border border-hairline bg-surface">
          {/* Header */}
          <div className="grid grid-cols-[200px_180px_200px_1fr_130px] border-b border-hairline px-6 py-3 font-mono text-label uppercase text-text-muted">
            <span>Timestamp</span>
            <span>User</span>
            <span>Action</span>
            <span>Detail</span>
            <span>IP</span>
          </div>
          {/* Virtualised rows (TanStack Virtual, §14.2) */}
          <div ref={parentRef} className="overflow-auto" style={{ maxHeight: 600 }}>
            <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
              {virtualizer.getVirtualItems().map((v) => {
                const r = rows[v.index]!;
                return (
                  <div
                    key={r.logId}
                    className="grid grid-cols-[200px_180px_200px_1fr_130px] items-center border-b border-hairline px-6 text-body"
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: v.size,
                      transform: `translateY(${v.start}px)`,
                    }}
                  >
                    <span className="truncate font-mono text-data tabular-nums text-text-secondary">
                      {formatTimestamp(r.timestamp)}
                    </span>
                    <span className="truncate text-ink">{r.userName}</span>
                    <span className="truncate">
                      <Badge tone={r.actionPerformed.includes('FAILED') || r.actionPerformed.includes('UNAUTHORISED') ? 'danger' : 'neutral'} dot={false}>
                        {humanise(r.actionPerformed)}
                      </Badge>
                    </span>
                    <span className="truncate text-text-secondary">{r.detail}</span>
                    <span className="truncate font-mono text-label tabular-nums text-text-muted">
                      {r.ipAddress}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
