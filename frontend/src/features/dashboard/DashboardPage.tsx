import { lazy, Suspense } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, CalendarClock, ClipboardList, ShieldAlert } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Progress,
  RankBadge,
  Skeleton,
  Stat,
  StatusBadge,
} from '@/components/ui';
import { RationaleCard } from '@/components/prediction';
import { dashboardApi } from '@/api/endpoints';
import { useAuth } from '@/hooks/useAuth';
import { ROLE_LABELS } from '@/lib/constants';
import { formatCount, formatDate, formatDateRange, formatRating, formatRelative, formatScore, surname } from '@/lib/format';
import type { DashboardData } from '@/types/api';

const TrendLine = lazy(() => import('@/components/charts/TrendLine').then((m) => ({ default: m.TrendLine })));
const DistributionBar = lazy(() =>
  import('@/components/charts/DistributionBar').then((m) => ({ default: m.DistributionBar })),
);

/**
 * Dashboard (§11.2) — role-adaptive, one route. Never shows a user a widget they
 * cannot act on; each role's blocking action is surfaced first.
 */
export function DashboardPage() {
  const { user, role } = useAuth();
  const query = useQuery({
    queryKey: ['dashboard', role, user?.userId],
    queryFn: () => dashboardApi.getDashboard(role!, user?.userId),
    enabled: Boolean(role),
  });

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow={role ? ROLE_LABELS[role] : undefined}
        title={user ? `Welcome, ${surname(user.fullName)}` : 'Dashboard'}
        description="Your decision-support overview for trainer allocation."
      />

      {query.isError ? (
        <Card>
          <CardBody>
            <ErrorState onRetry={() => query.refetch()} />
          </CardBody>
        </Card>
      ) : query.isLoading || !query.data ? (
        <DashboardSkeleton />
      ) : role === 'TRAINING_ADMINISTRATOR' ? (
        <AdministratorDashboard data={query.data} />
      ) : role === 'TRAINING_OFFICER' ? (
        <OfficerDashboard data={query.data} />
      ) : role === 'TRAINER' ? (
        <TrainerDashboard data={query.data} />
      ) : (
        <SystemAdminDashboard data={query.data} />
      )}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-md" />
        ))}
      </div>
      <Skeleton className="h-80 rounded-md" />
    </div>
  );
}

// --- Training Administrator ------------------------------------------------

function AdministratorDashboard({ data }: { data: DashboardData }) {
  const navigate = useNavigate();
  return (
    <>
      <div className="grid items-stretch gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Awaiting my approval" value={formatCount(data.summary.awaitingApproval)} />
        <Stat label="Predictions ready" value={formatCount(data.summary.predictionsReady)} />
        <Stat label="Allocations this quarter" value={formatCount(data.summary.allocationsThisQuarter)} />
        <Stat label="Evaluations outstanding" value={formatCount(data.summary.evaluationsOutstanding)} />
      </div>

      {/* Prediction queue — the action, first */}
      <Card>
        <CardHeader>
          <CardTitle>Prediction queue</CardTitle>
        </CardHeader>
        <CardBody>
          {!data.predictionQueue || data.predictionQueue.length === 0 ? (
            <EmptyState
              compact
              icon={<ClipboardList size={20} className="shrink-0" />}
              title="No predictions awaiting review"
              description="When an Officer defines requirements and runs a prediction, it appears here."
            />
          ) : (
            <ul className="flex flex-col divide-y divide-hairline">
              {data.predictionQueue.map((q) => (
                <li key={q.programmeId} className="flex flex-wrap items-center gap-4 py-3">
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-body font-semibold text-ink">{q.title}</span>
                    <span className="font-mono text-label text-text-muted">
                      {q.category} · {formatCount(q.rankedCount)} ranked · {formatRelative(q.generatedDate)}
                    </span>
                  </span>
                  <span className="flex items-center gap-2">
                    <RankBadge rank={1} size="sm" />
                    <span className="flex flex-col">
                      <span className="text-body-sm font-medium text-ink">
                        {q.topTrainerRank} {q.topTrainerName}
                      </span>
                      <span className="font-mono text-label text-text-muted">
                        {formatScore(q.topScore)} / 100
                      </span>
                    </span>
                  </span>
                  <Button size="sm" onClick={() => navigate(`/programmes/${q.programmeId}/prediction`)}>
                    Review ranking
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2 xl:items-stretch">
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Trainer utilisation</CardTitle>
            <p className="mt-1 text-body-sm text-text-muted">
              Allocations per trainer — a long tail here means the same names are being reused.
            </p>
          </CardHeader>
          <CardBody>
            {data.utilisation && data.utilisation.length > 0 ? (
              <Suspense fallback={<Skeleton className="h-64 rounded-md" />}>
                <DistributionBar data={data.utilisation} layout="vertical" height={300} />
              </Suspense>
            ) : (
              <EmptyState compact title="No allocations yet" />
            )}
          </CardBody>
        </Card>

        <Card className="h-full">
          <CardHeader>
            <CardTitle>Performance trend</CardTitle>
            <p className="mt-1 text-body-sm text-text-muted">Mean evaluation score by quarter.</p>
          </CardHeader>
          <CardBody>
            {data.performanceTrend && data.performanceTrend.length > 0 ? (
              <Suspense fallback={<Skeleton className="h-64 rounded-md" />}>
                <TrendLine data={data.performanceTrend} domain={[1, 5]} height={300} valueSuffix=" / 5" />
              </Suspense>
            ) : (
              <EmptyState compact title="No evaluations recorded yet" />
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent activity</CardTitle>
        </CardHeader>
        <CardBody>
          {data.recentActivity && data.recentActivity.length > 0 ? (
            <ul className="flex flex-col divide-y divide-hairline">
              {data.recentActivity.map((a) => (
                <li key={a.logId} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                  <span className="text-body-sm text-ink">{a.detail}</span>
                  <span className="font-mono text-label text-text-muted">
                    {a.userName} · {formatRelative(a.timestamp)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState compact title="No recent activity" />
          )}
        </CardBody>
      </Card>
    </>
  );
}

// --- Training Officer ------------------------------------------------------

function OfficerDashboard({ data }: { data: DashboardData }) {
  const navigate = useNavigate();
  const needing = data.requestsNeedingRequirements ?? [];
  return (
    <>
      {/* The blocking action, surfaced first */}
      <Card className={needing.length > 0 ? 'border-warning-border' : undefined}>
        <CardHeader>
          <CardTitle>Requests needing requirements</CardTitle>
          <p className="mt-1 text-body-sm text-text-muted">
            A request cannot be matched to trainers until its requirements are defined.
          </p>
        </CardHeader>
        <CardBody>
          {needing.length === 0 ? (
            <EmptyState compact title="Nothing outstanding" description="Every request has its requirements defined." />
          ) : (
            <ul className="flex flex-col divide-y divide-hairline">
              {needing.map((p) => (
                <li key={p.programmeId} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-body font-medium text-ink">{p.title}</span>
                    <span className="font-mono text-label text-text-muted">
                      {p.category} · {formatDateRange(p.startDate, p.endDate)}
                    </span>
                  </span>
                  <Button size="sm" onClick={() => navigate(`/programmes/${p.programmeId}/requirements`)}>
                    Define requirements
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2 lg:items-stretch">
        <Card className="h-full">
          <CardHeader>
            <CardTitle>My requests by status</CardTitle>
          </CardHeader>
          <CardBody>
            {data.myRequestsByStatus && data.myRequestsByStatus.length > 0 ? (
              <ul className="flex flex-col gap-3">
                {data.myRequestsByStatus.map((b) => (
                  <li key={b.label} className="flex items-center gap-3">
                    <span className="w-40 shrink-0 text-body-sm text-text-secondary">{b.label}</span>
                    <Progress value={(b.value / Math.max(...data.myRequestsByStatus!.map((x) => x.value))) * 100} className="flex-1" />
                    <span className="w-8 shrink-0 text-right font-mono text-data tabular-nums text-ink">{b.value}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState compact title="No requests yet" description="Create one to start matching trainers." />
            )}
          </CardBody>
        </Card>

        <Card className="h-full">
          <CardHeader>
            <CardTitle>
              <span className="flex items-center gap-2">
                <CalendarClock size={16} className="shrink-0 text-text-muted" />
                Upcoming in the next 30 days
              </span>
            </CardTitle>
          </CardHeader>
          <CardBody>
            {data.upcoming && data.upcoming.length > 0 ? (
              <ul className="flex flex-col divide-y divide-hairline">
                {data.upcoming.map((p) => (
                  <li key={p.programmeId} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                    <Link to={`/programmes/${p.programmeId}`} className="min-w-0 truncate text-body text-ink hover:underline">
                      {p.title}
                    </Link>
                    <span className="font-mono text-label tabular-nums text-text-muted">
                      {formatDateRange(p.startDate, p.endDate)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState compact title="Nothing scheduled in the next 30 days" />
            )}
          </CardBody>
        </Card>
      </div>
    </>
  );
}

// --- Trainer ---------------------------------------------------------------

function TrainerDashboard({ data }: { data: DashboardData }) {
  const navigate = useNavigate();
  const invitations = data.pendingInvitations ?? [];
  return (
    <>
      {/* The action, first */}
      <Card className={invitations.length > 0 ? 'border-info-border' : undefined}>
        <CardHeader>
          <CardTitle>Pending assignment invitations</CardTitle>
        </CardHeader>
        <CardBody>
          {invitations.length === 0 ? (
            <EmptyState compact title="No pending invitations" description="You will be notified when you are recommended for a course." />
          ) : (
            <ul className="flex flex-col gap-4">
              {invitations.map((a) => (
                <li key={a.allocationId} className="flex flex-col gap-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-body font-semibold text-ink">{a.programmeTitle}</span>
                    <StatusBadge kind="allocation" value={a.status} />
                  </div>
                  <RationaleCard rationale={a.frozenRationale} />
                  <div>
                    <Button size="sm" onClick={() => navigate('/my-assignments')}>
                      Respond
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <div className="grid items-stretch gap-6 sm:grid-cols-3">
        <Stat
          label="My mean evaluation"
          value={data.myMeanScore === null || data.myMeanScore === undefined ? '—' : formatRating(data.myMeanScore)}
          hint="out of 5"
        />
        <Stat label="Profile completeness" value={`${data.profileCompleteness ?? 0}%`} />
        <Stat label="Evaluations recorded" value={formatCount(data.myScoreTrend?.length ?? 0)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2 lg:items-stretch">
        <Card className="h-full">
          <CardHeader>
            <CardTitle>My evaluation trend</CardTitle>
          </CardHeader>
          <CardBody>
            {data.myScoreTrend && data.myScoreTrend.length > 0 ? (
              <Suspense fallback={<Skeleton className="h-56 rounded-md" />}>
                <TrendLine data={data.myScoreTrend} domain={[1, 5]} height={240} valueSuffix=" / 5" />
              </Suspense>
            ) : (
              <EmptyState compact title="No evaluations yet" />
            )}
          </CardBody>
        </Card>

        <Card className="h-full">
          <CardHeader>
            <CardTitle>Profile completeness</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="flex flex-col gap-3">
              <Progress value={data.profileCompleteness ?? 0} />
              <p className="text-body-sm text-text-muted">
                A fuller profile raises the confidence the system has in your ranking.
              </p>
              <div>
                <Button variant="secondary" size="sm" onClick={() => navigate('/my-profile')} icon={<ArrowRight size={16} className="shrink-0" />}>
                  Complete my profile
                </Button>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    </>
  );
}

// --- System Administrator --------------------------------------------------

function SystemAdminDashboard({ data }: { data: DashboardData }) {
  const runtimes = (data.predictionRuntimes ?? []).map((r) => ({
    label: formatDate(r.date),
    value: Math.round(r.ms),
  }));
  return (
    <>
      <div className="grid items-stretch gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Active users" value={formatCount(data.activeUsers ?? 0)} />
        <Stat label="Failed sign-ins (24h)" value={formatCount(data.failedSignins24h ?? 0)} icon={<ShieldAlert size={16} className="shrink-0" />} />
        <Stat label="Locked accounts" value={formatCount(data.lockedAccounts ?? 0)} />
        <Stat label="Audit entries" value={formatCount(data.auditVolume ?? 0)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2 lg:items-stretch">
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Active users by role</CardTitle>
          </CardHeader>
          <CardBody>
            {data.usersByRole && data.usersByRole.length > 0 ? (
              <Suspense fallback={<Skeleton className="h-56 rounded-md" />}>
                <DistributionBar data={data.usersByRole} height={260} />
              </Suspense>
            ) : (
              <EmptyState compact title="No users" />
            )}
          </CardBody>
        </Card>

        <Card className="h-full">
          <CardHeader>
            <CardTitle>Prediction run time</CardTitle>
            <p className="mt-1 text-body-sm text-text-muted">
              Against the 10-second NFR-01 threshold.
            </p>
          </CardHeader>
          <CardBody>
            {runtimes.length > 0 ? (
              <Suspense fallback={<Skeleton className="h-56 rounded-md" />}>
                <TrendLine
                  data={runtimes}
                  height={260}
                  valueSuffix="ms"
                  reference={{ value: 10000, label: 'NFR-01 threshold' }}
                />
              </Suspense>
            ) : (
              <EmptyState compact title="No prediction runs yet" />
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardBody>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-body text-text-secondary">Last backup</span>
            <span className="font-mono text-data tabular-nums text-ink">
              {data.lastBackupAt ? formatRelative(data.lastBackupAt) : '—'}
            </span>
          </div>
        </CardBody>
      </Card>
    </>
  );
}
