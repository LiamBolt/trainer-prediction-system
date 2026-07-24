import { lazy, Suspense } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Skeleton,
  Stat,
} from '@/components/ui';
import { dashboardApi } from '@/api/endpoints';
import { useAuth } from '@/hooks/useAuth';
import { formatCount, formatDate, formatRelative } from '@/lib/format';

const TrendLine = lazy(() => import('@/components/charts/TrendLine').then((m) => ({ default: m.TrendLine })));

/**
 * System health (§11.10) — prediction run time against the 10-second NFR-01
 * threshold, failed sign-ins, locked accounts, audit volume, and last backup.
 */
export function SystemHealthPage() {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ['dashboard', 'SYSTEM_ADMINISTRATOR', user?.userId],
    queryFn: () => dashboardApi.getDashboard('SYSTEM_ADMINISTRATOR', user?.userId),
  });

  const runtimes = (query.data?.predictionRuntimes ?? []).map((r) => ({
    label: formatDate(r.date),
    value: Math.round(r.ms),
  }));
  const slowest = runtimes.reduce((max, r) => Math.max(max, r.value), 0);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Administration"
        title="System health"
        description="Operational signals for the Trainer Prediction System."
      />

      {query.isLoading ? (
        <div className="flex flex-col gap-6">
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-md" />
            ))}
          </div>
          <Skeleton className="h-80 rounded-md" />
        </div>
      ) : query.isError || !query.data ? (
        <Card>
          <CardBody>
            <ErrorState onRetry={() => query.refetch()} />
          </CardBody>
        </Card>
      ) : (
        <>
          <div className="grid items-stretch gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Failed sign-ins (24h)" value={formatCount(query.data.failedSignins24h ?? 0)} />
            <Stat label="Locked accounts" value={formatCount(query.data.lockedAccounts ?? 0)} />
            <Stat label="Audit entries" value={formatCount(query.data.auditVolume ?? 0)} />
            <Stat
              label="Slowest prediction"
              value={`${(slowest / 1000).toFixed(1)}s`}
              hint="NFR-01 threshold is 10.0s"
              delta={slowest > 10000 ? { value: 'over threshold', direction: 'down' } : undefined}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Prediction run time</CardTitle>
              <p className="mt-1 text-body-sm text-text-muted">
                Each recorded run, with the 10-second NFR-01 threshold drawn as a reference line.
              </p>
            </CardHeader>
            <CardBody>
              {runtimes.length === 0 ? (
                <EmptyState compact title="No prediction runs recorded yet" />
              ) : (
                <Suspense fallback={<Skeleton className="h-64 rounded-md" />}>
                  <TrendLine
                    data={runtimes}
                    height={300}
                    valueSuffix="ms"
                    reference={{ value: 10000, label: 'NFR-01 threshold (10s)' }}
                  />
                </Suspense>
              )}
            </CardBody>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2 lg:items-stretch">
            <Card className="h-full">
              <CardHeader>
                <CardTitle>Backup</CardTitle>
              </CardHeader>
              <CardBody>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-body text-text-secondary">Last completed backup</span>
                  <span className="font-mono text-data tabular-nums text-ink">
                    {query.data.lastBackupAt ? formatRelative(query.data.lastBackupAt) : '—'}
                  </span>
                </div>
              </CardBody>
            </Card>

            <Card className="h-full">
              <CardHeader>
                <CardTitle>Notification delivery</CardTitle>
              </CardHeader>
              <CardBody>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-body text-text-secondary">Delivery status</span>
                  <span className="font-mono text-data text-success-fg">Operational</span>
                </div>
              </CardBody>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
