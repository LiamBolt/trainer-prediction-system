import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowRight, ListChecks, ScrollText } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  KeyValueList,
  Skeleton,
  ErrorState,
  StatusBadge,
  EmptyState,
  toast,
} from '@/components/ui';
import { ProgrammeTimeline } from '@/components/prediction/ProgrammeTimeline';
import { RoleGate } from '@/components/routing/RoleGate';
import { programmesApi, predictionsApi } from '@/api/endpoints';
import {
  QUALIFICATION_LABELS,
  PROGRAMME_STATUS_LABELS,
} from '@/lib/constants';
import { formatDate, formatDateRange, formatTimestamp, programmeRegistry } from '@/lib/format';

/**
 * Request detail (§11.3) — particulars, the swimlane timeline, the allocation if
 * one exists, and this request's audit trail. If the requirements changed since
 * the last ranking, a persistent amber banner offers a re-run (FR-05).
 */
export function ProgrammeDetailPage() {
  const { id } = useParams();
  const programmeId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['programme', programmeId],
    queryFn: () => programmesApi.getProgramme(programmeId),
    enabled: Number.isFinite(programmeId),
  });

  const rerun = useMutation({
    mutationFn: () => predictionsApi.generatePrediction(programmeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['programme', programmeId] });
      queryClient.invalidateQueries({ queryKey: ['prediction', programmeId] });
      toast.success('Prediction re-run with the current requirements.');
      navigate(`/programmes/${programmeId}/prediction`);
    },
  });

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-40 rounded-md" />
        <Skeleton className="h-64 rounded-md" />
      </div>
    );
  }
  if (query.isError || !query.data) {
    return (
      <Card>
        <CardBody>
          <ErrorState onRetry={() => query.refetch()} />
        </CardBody>
      </Card>
    );
  }

  const { programme, allocation, hasRun, auditTrail } = query.data;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow={programmeRegistry(programme.programmeId)}
        title={programme.title}
        breadcrumbs={[{ label: 'Training requests', to: '/programmes' }, { label: programme.title }]}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge kind="programme" value={programme.status} />
            {hasRun && (
              <Button variant="secondary" onClick={() => navigate(`/programmes/${programmeId}/prediction`)} icon={<ListChecks size={16} className="shrink-0" />}>
                View ranking
              </Button>
            )}
            {!programme.requiredSpecialization && (
              <RoleGate roles={['TRAINING_ADMINISTRATOR', 'TRAINING_OFFICER']}>
                <Button onClick={() => navigate(`/programmes/${programmeId}/requirements`)} icon={<ArrowRight size={16} className="shrink-0" />}>
                  Define requirements
                </Button>
              </RoleGate>
            )}
          </div>
        }
      />

      {/* FR-05 re-rank banner */}
      {programme.requirementsChangedSincePrediction && (
        <div className="flex flex-col gap-3 rounded-md border border-warning-border bg-warning-bg p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2 text-warning-fg">
            <AlertTriangle size={20} className="mt-0.5 shrink-0" />
            <p className="text-body">
              Requirements changed since the last ranking. Re-run to see current recommendations.
            </p>
          </div>
          <Button onClick={() => rerun.mutate()} loading={rerun.isPending}>
            Re-run prediction
          </Button>
        </div>
      )}

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Progress</CardTitle>
        </CardHeader>
        <CardBody>
          <ProgrammeTimeline status={programme.status} />
        </CardBody>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2 lg:items-stretch">
        {/* Particulars */}
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Particulars</CardTitle>
          </CardHeader>
          <CardBody>
            <KeyValueList
              items={[
                { label: 'Registry no.', value: programmeRegistry(programme.programmeId), mono: true },
                { label: 'Category', value: programme.category },
                {
                  label: 'Specialisation',
                  value: programme.requiredSpecialization || 'Not yet defined',
                },
                {
                  label: 'Min. experience',
                  value: `${programme.minimumExperience} years`,
                  mono: true,
                },
                {
                  label: 'Min. qualification',
                  value: programme.minimumQualification
                    ? QUALIFICATION_LABELS[programme.minimumQualification]
                    : 'Any',
                },
                { label: 'Dates', value: formatDateRange(programme.startDate, programme.endDate), mono: true },
                { label: 'Location', value: programme.location },
                { label: 'Status', value: PROGRAMME_STATUS_LABELS[programme.status] },
                { label: 'Created by', value: programme.createdByName },
                { label: 'Created', value: formatDate(programme.createdAt), mono: true },
              ]}
            />
          </CardBody>
        </Card>

        {/* Allocation */}
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Allocation</CardTitle>
          </CardHeader>
          <CardBody>
            {allocation ? (
              <div className="flex flex-col gap-4">
                <KeyValueList
                  items={[
                    { label: 'Registry no.', value: allocation.registryNumber, mono: true },
                    { label: 'Approved by', value: allocation.approvedByName },
                    { label: 'Approved', value: formatDate(allocation.approvalDate), mono: true },
                    { label: 'Score', value: `${allocation.frozenScore.toFixed(1)} out of 100`, mono: true },
                  ]}
                />
                <div className="flex items-center gap-3">
                  <StatusBadge kind="allocation" value={allocation.status} />
                  <Button asChild variant="secondary" size="sm">
                    <Link to={`/allocations/${allocation.allocationId}`}>Open decision receipt</Link>
                  </Button>
                </div>
              </div>
            ) : (
              <EmptyState
                compact
                title="No allocation yet"
                description={
                  hasRun
                    ? 'Open the ranking and approve a trainer to create one.'
                    : 'Define the requirements and run a prediction first.'
                }
                action={
                  hasRun ? (
                    <Button size="sm" onClick={() => navigate(`/programmes/${programmeId}/prediction`)}>
                      View ranking
                    </Button>
                  ) : undefined
                }
              />
            )}
          </CardBody>
        </Card>
      </div>

      {/* Audit trail */}
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-2">
              <ScrollText size={16} className="shrink-0 text-text-muted" />
              Audit trail for this request
            </span>
          </CardTitle>
        </CardHeader>
        <CardBody>
          {auditTrail.length === 0 ? (
            <p className="text-body-sm text-text-muted">No entries recorded yet.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-hairline">
              {auditTrail.map((entry) => (
                <li key={entry.logId} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                  <span className="text-body text-ink">{entry.detail}</span>
                  <span className="font-mono text-label tabular-nums text-text-muted">
                    {entry.userName} · {formatTimestamp(entry.timestamp)}
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
