import { lazy, Suspense, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
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
import { trainersApi } from '@/api/endpoints';
import { useAuth } from '@/hooks/useAuth';
import { formatDate, formatRating } from '@/lib/format';

const TrendLine = lazy(() =>
  import('@/components/charts/TrendLine').then((m) => ({ default: m.TrendLine })),
);

/** My performance (§11.7) — evaluation history, mean score, trend, and the
 *  evaluator comments. Read-only. */
export function MyPerformancePage() {
  const { user } = useAuth();

  const query = useQuery({
    queryKey: ['me', 'trainer', user?.userId],
    queryFn: () => trainersApi.getMyTrainer(user!.userId),
    enabled: Boolean(user),
  });
  const trainer = query.data;

  const history = useMemo(
    () =>
      [...(trainer?.performanceHistory ?? [])].sort(
        (a, b) => dayjs(b.evaluationDate).valueOf() - dayjs(a.evaluationDate).valueOf(),
      ),
    [trainer],
  );
  const trend = useMemo(
    () =>
      [...(trainer?.performanceHistory ?? [])]
        .sort((a, b) => dayjs(a.evaluationDate).valueOf() - dayjs(b.evaluationDate).valueOf())
        .map((e) => ({ label: dayjs(e.evaluationDate).format('MMM YY'), value: e.scoreAwarded })),
    [trainer],
  );
  const mean =
    history.length > 0 ? history.reduce((s, e) => s + e.scoreAwarded, 0) / history.length : null;

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 rounded-md" />
        <Skeleton className="h-80 rounded-md" />
      </div>
    );
  }
  if (query.isError || !trainer) {
    return (
      <Card>
        <CardBody>
          <ErrorState onRetry={() => query.refetch()} />
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Trainer"
        title="My performance"
        description="How officers have rated the courses you delivered. These scores inform your future rankings."
      />

      <div className="grid items-stretch gap-6 sm:grid-cols-3">
        <Stat label="Mean evaluation" value={mean === null ? '—' : formatRating(mean)} hint="out of 5" />
        <Stat label="Courses evaluated" value={history.length} />
        <Stat
          label="Most recent"
          value={history[0] ? formatRating(history[0].scoreAwarded) : '—'}
          hint={history[0] ? formatDate(history[0].evaluationDate) : undefined}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Scores over time</CardTitle>
        </CardHeader>
        <CardBody>
          {trend.length === 0 ? (
            <EmptyState
              compact
              title="No evaluations yet"
              description="Once you have delivered a course and been evaluated, your scores appear here."
            />
          ) : (
            <Suspense fallback={<Skeleton className="h-60 rounded-md" />}>
              <TrendLine data={trend} domain={[1, 5]} valueSuffix=" / 5" />
            </Suspense>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Evaluator comments</CardTitle>
        </CardHeader>
        <CardBody>
          {history.length === 0 ? (
            <EmptyState compact title="No comments yet" />
          ) : (
            <ul className="flex flex-col divide-y divide-hairline">
              {history.map((e) => (
                <li key={e.evaluationId} className="flex flex-col gap-1 py-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="text-body font-medium text-ink">{e.programmeTitle}</span>
                    <span className="font-mono text-data tabular-nums text-ink">
                      {formatRating(e.scoreAwarded)}
                      <span className="text-text-disabled"> / 5</span>
                    </span>
                  </div>
                  <p className="text-body-sm text-text-muted">{e.evaluatorComments}</p>
                  <span className="font-mono text-label text-text-muted">
                    {e.evaluatedByName} · {formatDate(e.evaluationDate)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
