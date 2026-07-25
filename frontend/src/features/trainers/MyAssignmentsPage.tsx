import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarCheck, Check, MapPin, X } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  ErrorState,
  FormField,
  Skeleton,
  StatusBadge,
  Textarea,
  Tooltip,
  toast,
} from '@/components/ui';
import { RationaleCard } from '@/components/prediction';
import { allocationsApi, trainersApi } from '@/api/endpoints';
import { useAuth } from '@/hooks/useAuth';
import { formatDateRange } from '@/lib/format';
import { declineSchema, type DeclineForm } from '@/schemas/evaluation';
import type { AllocationListItem } from '@/types/api';

/**
 * My assignments (FR-09). Pending invitations first, each showing the programme,
 * dates, location, and WHY this trainer was selected — the trainer deserves to
 * see the rationale too. Declining requires a reason; Submit stays disabled until
 * one is written, and the dialog says so.
 */
export function MyAssignmentsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [declining, setDeclining] = useState<AllocationListItem | null>(null);

  const trainerQuery = useQuery({
    queryKey: ['me', 'trainer', user?.userId],
    queryFn: () => trainersApi.getMyTrainer(),
    enabled: Boolean(user),
  });
  const trainerId = trainerQuery.data?.trainerId;

  const allocationsQuery = useQuery({
    queryKey: ['allocations', 'mine', trainerId],
    queryFn: () => allocationsApi.listAllocations({ trainerId, pageSize: 100 }),
    enabled: Boolean(trainerId),
  });

  const form = useForm<DeclineForm>({
    resolver: zodResolver(declineSchema),
    mode: 'onChange',
    defaultValues: { reason: '' },
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['allocations'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  };

  const accept = useMutation({
    mutationFn: (allocationId: number) => allocationsApi.acceptAssignment(allocationId),
    onSuccess: () => {
      invalidate();
      toast.success('Accepted', { description: 'The Training Administrator has been notified.' });
    },
    onError: () => toast.error('Could not accept the assignment. Please try again.'),
  });

  const decline = useMutation({
    mutationFn: (data: { allocationId: number; reason: string }) =>
      allocationsApi.declineAssignment({ allocationId: data.allocationId, reason: data.reason }),
    onSuccess: () => {
      invalidate();
      setDeclining(null);
      form.reset();
      toast.success('Declined', {
        description: 'The Administrator can now promote the next-ranked candidate.',
      });
    },
    onError: () => toast.error('Could not decline the assignment. Please try again.'),
  });

  const items = allocationsQuery.data?.items ?? [];
  const pending = items.filter((a) => a.status === 'PENDING_TRAINER');
  const upcoming = items.filter((a) => a.status === 'CONFIRMED');
  const past = items.filter((a) => ['CONDUCTED', 'EVALUATED', 'DECLINED', 'WITHDRAWN'].includes(a.status));

  const isLoading = trainerQuery.isLoading || allocationsQuery.isLoading;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Trainer"
        title="My assignments"
        description="Invitations to deliver training, and the courses you have already been allocated."
      />

      {isLoading ? (
        <div className="flex flex-col gap-6">
          <Skeleton className="h-56 rounded-md" />
          <Skeleton className="h-40 rounded-md" />
        </div>
      ) : allocationsQuery.isError ? (
        <Card>
          <CardBody>
            <ErrorState onRetry={() => allocationsQuery.refetch()} />
          </CardBody>
        </Card>
      ) : (
        <>
          {/* Pending invitations — the action, first */}
          <section className="flex flex-col gap-4">
            <h2 className="text-h2 text-ink">Pending invitations</h2>
            {pending.length === 0 ? (
              <Card>
                <CardBody>
                  <EmptyState
                    compact
                    icon={<CalendarCheck size={20} className="shrink-0" />}
                    title="No pending invitations"
                    description="When you are recommended for a course, the invitation will appear here."
                  />
                </CardBody>
              </Card>
            ) : (
              pending.map((a) => (
                <Card key={a.allocationId}>
                  <CardBody>
                    <div className="flex flex-col gap-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex flex-col gap-1">
                          <span className="text-h3 text-ink">{a.programmeTitle}</span>
                          <span className="flex flex-wrap items-center gap-3 font-mono text-label text-text-muted">
                            <span>{a.registryNumber}</span>
                            {a.programmeStartDate && (
                              <span>{formatDateRange(a.programmeStartDate, a.programmeEndDate)}</span>
                            )}
                            <span className="inline-flex items-center gap-1">
                              <MapPin size={12} className="shrink-0" />
                              {a.programmeLocation}
                            </span>
                          </span>
                        </div>
                        <StatusBadge kind="allocation" value={a.status} />
                      </div>

                      <div className="flex flex-col gap-2">
                        <span className="font-mono text-label uppercase text-text-muted">
                          Why you were selected
                        </span>
                        <RationaleCard rationale={a.frozenRationale} />
                      </div>

                      <div className="flex flex-wrap gap-3 border-t border-hairline pt-4">
                        <Button
                          onClick={() => accept.mutate(a.allocationId)}
                          loading={accept.isPending}
                          icon={<Check size={16} className="shrink-0" />}
                        >
                          Accept
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => setDeclining(a)}
                          icon={<X size={16} className="shrink-0" />}
                        >
                          Decline
                        </Button>
                      </div>
                    </div>
                  </CardBody>
                </Card>
              ))
            )}
          </section>

          {/* Confirmed upcoming */}
          <Card>
            <CardHeader>
              <CardTitle>Confirmed upcoming courses</CardTitle>
            </CardHeader>
            <CardBody>
              {upcoming.length === 0 ? (
                <EmptyState compact title="No confirmed courses" />
              ) : (
                <ul className="flex flex-col divide-y divide-hairline">
                  {upcoming.map((a) => (
                    <li key={a.allocationId} className="flex flex-wrap items-center justify-between gap-2 py-3">
                      <span className="flex flex-col">
                        <span className="text-body font-medium text-ink">{a.programmeTitle}</span>
                        <span className="font-mono text-label text-text-muted">
                          {a.registryNumber} · {a.programmeLocation}
                        </span>
                      </span>
                      <span className="font-mono text-data tabular-nums text-text-secondary">
                        {a.programmeStartDate && formatDateRange(a.programmeStartDate, a.programmeEndDate)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          {/* Past */}
          <Card>
            <CardHeader>
              <CardTitle>Past courses</CardTitle>
            </CardHeader>
            <CardBody>
              {past.length === 0 ? (
                <EmptyState compact title="No past courses yet" />
              ) : (
                <ul className="flex flex-col divide-y divide-hairline">
                  {past.map((a) => (
                    <li key={a.allocationId} className="flex flex-wrap items-center justify-between gap-2 py-3">
                      <span className="flex flex-col">
                        <span className="text-body font-medium text-ink">{a.programmeTitle}</span>
                        <span className="font-mono text-label text-text-muted">{a.registryNumber}</span>
                      </span>
                      <StatusBadge kind="allocation" value={a.status} />
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </>
      )}

      {/* Decline dialog — reason required (FR-09) */}
      <Dialog open={Boolean(declining)} onOpenChange={(o) => !o && setDeclining(null)}>
        <DialogContent size="md">
          <DialogHeader>
            <DialogTitle>Decline this assignment</DialogTitle>
            <DialogDescription>
              A reason is required so the Training Administrator can allocate someone else.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <FormField
              label="Reason for declining"
              required
              error={form.formState.errors.reason?.message}
            >
              <Textarea
                {...form.register('reason')}
                placeholder="e.g. Committed to court testimony in Jinja for the same period."
                maxLength={280}
                showCount
              />
            </FormField>
          </DialogBody>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setDeclining(null)} disabled={decline.isPending}>
              Cancel
            </Button>
            {form.formState.isValid ? (
              <Button
                variant="danger"
                loading={decline.isPending}
                onClick={() =>
                  declining &&
                  decline.mutate({ allocationId: declining.allocationId, reason: form.getValues('reason') })
                }
              >
                Decline assignment
              </Button>
            ) : (
              <Tooltip content="Write a reason before declining." onDisabled>
                <Button variant="danger" disabled>
                  Decline assignment
                </Button>
              </Tooltip>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
