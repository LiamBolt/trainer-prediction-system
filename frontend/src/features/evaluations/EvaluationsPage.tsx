import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ClipboardCheck } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Skeleton,
} from '@/components/ui';
import { evaluationsApi } from '@/api/endpoints';
import { formatDate, formatRating } from '@/lib/format';

/**
 * Performance evaluations (FR-10) — two sections: allocations awaiting evaluation
 * (status CONDUCTED) and recorded evaluations. The Record control is only enabled
 * once the training has been marked as conducted; when disabled it says why.
 */
export function EvaluationsPage() {
  const navigate = useNavigate();
  const query = useQuery({
    queryKey: ['evaluations'],
    queryFn: () => evaluationsApi.listEvaluations(),
  });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Evaluations"
        title="Performance evaluations"
        description="Recording a score closes the loop: it informs how this trainer is ranked for future courses."
      />

      {query.isLoading ? (
        <div className="flex flex-col gap-6">
          <Skeleton className="h-48 rounded-md" />
          <Skeleton className="h-64 rounded-md" />
        </div>
      ) : query.isError || !query.data ? (
        <Card>
          <CardBody>
            <ErrorState onRetry={() => query.refetch()} />
          </CardBody>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Awaiting evaluation</CardTitle>
            </CardHeader>
            <CardBody>
              {query.data.awaiting.length === 0 ? (
                <EmptyState
                  compact
                  icon={<ClipboardCheck size={20} className="shrink-0" />}
                  title="Nothing awaiting evaluation"
                  description="Courses appear here once they have been marked as conducted."
                />
              ) : (
                <ul className="flex flex-col divide-y divide-hairline">
                  {query.data.awaiting.map((a) => (
                    <li key={a.allocationId} className="flex flex-wrap items-center justify-between gap-3 py-3">
                      <span className="flex min-w-0 flex-col">
                        <span className="truncate text-body font-medium text-ink">{a.programmeTitle}</span>
                        <span className="font-mono text-label text-text-muted">
                          {a.registryNumber} · {a.trainerRank} {a.trainerName}
                        </span>
                      </span>
                      <Button
                        size="sm"
                        onClick={() => navigate(`/evaluations/new/${a.allocationId}`)}
                      >
                        Record evaluation
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recorded</CardTitle>
            </CardHeader>
            <CardBody>
              {query.data.recorded.length === 0 ? (
                <EmptyState compact title="No evaluations recorded yet" />
              ) : (
                <ul className="flex flex-col divide-y divide-hairline">
                  {query.data.recorded.map((e) => (
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
        </>
      )}
    </div>
  );
}
