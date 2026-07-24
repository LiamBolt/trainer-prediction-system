import { useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, UserPlus, XCircle } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  ErrorState,
  KeyValueList,
  Skeleton,
  StatusBadge,
  toast,
} from '@/components/ui';
import { DecisionReceipt } from '@/components/prediction';
import { RoleGate } from '@/components/routing/RoleGate';
import { allocationsApi } from '@/api/endpoints';
import { exportElementToPdf } from '@/lib/pdf';
import { formatDate, formatDateRange, formatTimestamp } from '@/lib/format';

/**
 * Allocation detail — the Decision Receipt (§12.7, §11.5). Shows the frozen score
 * and breakdown as at approval, the approving officer, and the trainer's response.
 * When a trainer declines, a prominent panel offers "Promote next-ranked
 * candidate" and states plainly that the ORIGINAL ranking is reused — no new
 * prediction is run (FR-08).
 */
export function AllocationDetailPage() {
  const { id } = useParams();
  const allocationId = Number(id);
  const queryClient = useQueryClient();
  const receiptRef = useRef<HTMLDivElement>(null);
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  const query = useQuery({
    queryKey: ['allocation', allocationId],
    queryFn: () => allocationsApi.getAllocation(allocationId),
    enabled: Number.isFinite(allocationId),
  });

  const promote = useMutation({
    mutationFn: () => allocationsApi.promoteNext(allocationId),
    onSuccess: (next) => {
      setPromoteOpen(false);
      queryClient.invalidateQueries({ queryKey: ['allocations'] });
      toast.success('Next-ranked candidate promoted', {
        description: `${next.registryNumber} created from the original ranking.`,
      });
    },
    onError: () => toast.error('There is no further candidate to promote.'),
  });

  const handleExport = async () => {
    if (!receiptRef.current) return;
    try {
      setExporting(true);
      await exportElementToPdf(receiptRef.current, `${query.data?.registryNumber.replace(/\//g, '-')}.pdf`);
      toast.success('Decision receipt exported');
    } catch {
      toast.error('Could not export the receipt.');
    } finally {
      setExporting(false);
    }
  };

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-96 rounded-md" />
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

  const a = query.data;
  const declined = a.status === 'DECLINED';

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Decision receipt"
        title={a.registryNumber}
        breadcrumbs={[{ label: 'Allocations', to: '/allocations' }, { label: a.registryNumber }]}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge kind="allocation" value={a.status} />
            <Button
              variant="secondary"
              onClick={handleExport}
              loading={exporting}
              icon={<Download size={16} className="shrink-0" />}
            >
              Export PDF
            </Button>
          </div>
        }
      />

      {/* FR-08 — declined: promote the next candidate, reusing the ranking */}
      {declined && (
        <Card className="border-danger-border">
          <CardBody>
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-danger-bg text-danger-fg">
                  <XCircle size={20} className="shrink-0" />
                </span>
                <div className="flex flex-col gap-1">
                  <span className="text-h3 text-ink">The trainer declined this assignment</span>
                  <p className="text-body text-text-secondary">
                    “{a.declineReason}”
                    {a.declinedAt && (
                      <span className="ml-2 font-mono text-label text-text-muted">
                        {formatTimestamp(a.declinedAt)}
                      </span>
                    )}
                  </p>
                  <p className="text-body-sm text-text-muted">
                    The original ranking is reused; no new prediction is run.
                  </p>
                </div>
              </div>
              <RoleGate roles={['TRAINING_ADMINISTRATOR']}>
                <Button onClick={() => setPromoteOpen(true)} icon={<UserPlus size={16} className="shrink-0" />}>
                  Promote next-ranked candidate
                </Button>
              </RoleGate>
            </div>
          </CardBody>
        </Card>
      )}

      {/* The receipt */}
      <DecisionReceipt
        ref={receiptRef}
        registryNumber={a.registryNumber}
        programmeTitle={a.programmeTitle}
        trainerName={a.trainerName}
        trainerRank={a.trainerRank}
        forceNumber={a.trainerForceNumber}
        station={a.trainerStation}
        frozenScore={a.frozenScore}
        frozenBreakdown={a.frozenBreakdown}
        frozenRankPosition={a.frozenRankPosition}
        frozenWeights={a.frozenWeights}
        weightsWereSimulated={a.weightsWereSimulated}
        approvedByName={a.approvedByName}
        approvalDate={a.approvalDate}
        remarks={a.remarks}
      />

      {/* Trainer response + course particulars */}
      <div className="grid gap-6 lg:grid-cols-2 lg:items-stretch">
        <Card className="h-full">
          <CardHeader>
            <CardTitle>Trainer response</CardTitle>
          </CardHeader>
          <CardBody>
            <KeyValueList
              items={[
                { label: 'Status', value: <StatusBadge kind="allocation" value={a.status} /> },
                {
                  label: 'Responded',
                  value: a.respondedAt ? formatTimestamp(a.respondedAt) : 'Awaiting response',
                  mono: Boolean(a.respondedAt),
                },
                ...(a.declineReason ? [{ label: 'Reason', value: a.declineReason }] : []),
              ]}
            />
          </CardBody>
        </Card>

        <Card className="h-full">
          <CardHeader>
            <CardTitle>Course particulars</CardTitle>
          </CardHeader>
          <CardBody>
            <KeyValueList
              items={[
                { label: 'Programme', value: a.programmeTitle },
                {
                  label: 'Dates',
                  value: a.programmeStartDate
                    ? formatDateRange(a.programmeStartDate, a.programmeEndDate)
                    : '—',
                  mono: true,
                },
                { label: 'Location', value: a.programmeLocation },
                { label: 'Approved', value: formatDate(a.approvalDate), mono: true },
              ]}
            />
          </CardBody>
        </Card>
      </div>

      <ConfirmDialog
        open={promoteOpen}
        onOpenChange={setPromoteOpen}
        title="Promote the next-ranked candidate?"
        description="This creates a new allocation for the next trainer in the original ranking. No new prediction is run."
        confirmLabel="Promote candidate"
        loading={promote.isPending}
        onConfirm={() => promote.mutate()}
      />
    </div>
  );
}
