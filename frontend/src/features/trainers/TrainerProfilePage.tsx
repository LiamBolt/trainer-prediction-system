import { lazy, Suspense, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Avatar,
  Badge,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  ErrorState,
  KeyValueList,
  Skeleton,
  Stat,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  EmptyState,
} from '@/components/ui';
import { AvailabilityPill } from '@/components/prediction';
import { trainersApi } from '@/api/endpoints';
import { PROFICIENCY_LABELS, QUALIFICATION_LABELS, RANK_FULL_NAMES } from '@/lib/constants';
import { formatDate, formatForceNumber, formatRating } from '@/lib/format';
import dayjs from 'dayjs';

const TrendLine = lazy(() =>
  import('@/components/charts/TrendLine').then((m) => ({ default: m.TrendLine })),
);

/** Trainer profile (§11.6) — tabs across overview, qualifications, specialisations,
 *  assignment history, and performance. */
export function TrainerProfilePage() {
  const { id } = useParams();
  const trainerId = Number(id);

  const query = useQuery({
    queryKey: ['trainer', trainerId],
    queryFn: () => trainersApi.getTrainer(trainerId),
    enabled: Number.isFinite(trainerId),
  });

  const trainer = query.data;

  const scoreTrend = useMemo(() => {
    if (!trainer) return [];
    return [...trainer.performanceHistory]
      .sort((a, b) => dayjs(a.evaluationDate).valueOf() - dayjs(b.evaluationDate).valueOf())
      .map((e) => ({ label: dayjs(e.evaluationDate).format('MMM YY'), value: e.scoreAwarded }));
  }, [trainer]);

  const meanScore = useMemo(() => {
    if (!trainer || trainer.performanceHistory.length === 0) return null;
    return (
      trainer.performanceHistory.reduce((s, e) => s + e.scoreAwarded, 0) /
      trainer.performanceHistory.length
    );
  }, [trainer]);

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-80" />
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
        eyebrow="Trainers"
        title={`${trainer.policeRank} ${trainer.fullName}`}
        breadcrumbs={[{ label: 'Trainer directory', to: '/trainers' }, { label: trainer.fullName }]}
      />

      {/* Header card */}
      <Card>
        <CardBody>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <Avatar name={trainer.fullName} size={40} />
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="text-h3 text-ink">
                {RANK_FULL_NAMES[trainer.policeRank]}
              </span>
              <span className="font-mono text-label text-text-muted">
                {formatForceNumber(trainer.forceNumber)} · {trainer.station} · {trainer.region}
              </span>
            </div>
            <AvailabilityPill status={trainer.availabilityStatus} />
          </div>
        </CardBody>
      </Card>

      {/* Stats */}
      <div className="grid items-stretch gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Years of service" value={trainer.yearsExperience} />
        <Stat label="Mean evaluation" value={meanScore === null ? '—' : formatRating(meanScore)} hint={`${trainer.performanceHistory.length} recorded`} />
        <Stat label="Current allocations" value={trainer.currentAllocations} />
        <Stat label="Profile completeness" value={`${trainer.profileCompleteness}%`} />
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="qualifications">Qualifications</TabsTrigger>
          <TabsTrigger value="specialisations">Specialisations</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <Card>
            <CardBody>
              <KeyValueList
                columns={2}
                items={[
                  { label: 'Rank', value: RANK_FULL_NAMES[trainer.policeRank] },
                  { label: 'Force no.', value: formatForceNumber(trainer.forceNumber), mono: true },
                  { label: 'Station', value: trainer.station },
                  { label: 'Region', value: trainer.region },
                  { label: 'Directorate', value: trainer.directorate },
                  { label: 'Contact', value: trainer.contactNumber, mono: true },
                  { label: 'Years of service', value: `${trainer.yearsExperience}`, mono: true },
                  {
                    label: 'Last assigned',
                    value: trainer.lastAssignedDate ? formatDate(trainer.lastAssignedDate) : 'Never',
                    mono: true,
                  },
                ]}
              />
            </CardBody>
          </Card>
        </TabsContent>

        <TabsContent value="qualifications">
          <Card>
            <CardBody>
              {trainer.qualifications.length === 0 ? (
                <EmptyState compact title="No qualifications recorded" />
              ) : (
                <ul className="flex flex-col divide-y divide-hairline">
                  {trainer.qualifications.map((q) => (
                    <li key={q.qualificationId} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                      <span className="flex flex-col">
                        <span className="text-body font-medium text-ink">{q.qualificationName}</span>
                        <span className="text-body-sm text-text-muted">{q.institutionName}</span>
                      </span>
                      <span className="flex items-center gap-3">
                        <Badge tone="neutral" dot={false}>
                          {QUALIFICATION_LABELS[q.qualificationLevel]}
                        </Badge>
                        <span className="font-mono text-data tabular-nums text-text-muted">{q.yearObtained}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </TabsContent>

        <TabsContent value="specialisations">
          <Card>
            <CardBody>
              {trainer.specializations.length === 0 ? (
                <EmptyState compact title="No specialisations recorded" />
              ) : (
                <ul className="flex flex-col divide-y divide-hairline">
                  {trainer.specializations.map((s) => (
                    <li key={s.specializationId} className="flex items-center justify-between gap-2 py-3">
                      <span className="text-body text-ink">{s.specializationArea}</span>
                      <Badge tone="info" dot={false}>
                        {PROFICIENCY_LABELS[s.proficiencyLevel]}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </TabsContent>

        <TabsContent value="performance">
          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Evaluation scores over time</CardTitle>
              </CardHeader>
              <CardBody>
                {scoreTrend.length === 0 ? (
                  <EmptyState
                    compact
                    title="No evaluations yet"
                    description="Scores appear here once this trainer has delivered and been evaluated."
                  />
                ) : (
                  <Suspense fallback={<Skeleton className="h-60 rounded-md" />}>
                    <TrendLine data={scoreTrend} domain={[1, 5]} valueSuffix=" / 5" />
                  </Suspense>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Past courses</CardTitle>
              </CardHeader>
              <CardBody>
                {trainer.performanceHistory.length === 0 ? (
                  <EmptyState compact title="No past courses recorded" />
                ) : (
                  <ul className="flex flex-col divide-y divide-hairline">
                    {[...trainer.performanceHistory]
                      .sort((a, b) => dayjs(b.evaluationDate).valueOf() - dayjs(a.evaluationDate).valueOf())
                      .map((e) => (
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
        </TabsContent>
      </Tabs>
    </div>
  );
}
