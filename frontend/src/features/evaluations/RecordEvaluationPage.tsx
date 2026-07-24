import { useNavigate, useParams } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  DatePicker,
  ErrorState,
  FormField,
  KeyValueList,
  Skeleton,
  StarRatingInput,
  Textarea,
  Tooltip,
  toast,
} from '@/components/ui';
import { allocationsApi, evaluationsApi } from '@/api/endpoints';
import { evaluationSchema, type EvaluationForm } from '@/schemas/evaluation';
import { surname } from '@/lib/format';

/**
 * Record evaluation (FR-10). The entry point is disabled unless the allocation is
 * CONDUCTED, with a tooltip saying so. On save, the toast states the consequence
 * plainly — closing the SRS feedback loop in language a user understands.
 */
export function RecordEvaluationPage() {
  const { allocationId: rawId } = useParams();
  const allocationId = Number(rawId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const allocationQuery = useQuery({
    queryKey: ['allocation', allocationId],
    queryFn: () => allocationsApi.getAllocation(allocationId),
    enabled: Number.isFinite(allocationId),
  });
  const allocation = allocationQuery.data;
  const conducted = allocation?.status === 'CONDUCTED';

  const form = useForm<EvaluationForm>({
    resolver: zodResolver(evaluationSchema),
    mode: 'onBlur',
    defaultValues: {
      scoreAwarded: 4,
      evaluatorComments: '',
      evaluationDate: new Date().toISOString().slice(0, 10),
    },
  });

  const mutation = useMutation({
    mutationFn: (data: EvaluationForm) =>
      evaluationsApi.recordEvaluation({
        allocationId,
        scoreAwarded: data.scoreAwarded,
        evaluatorComments: data.evaluatorComments,
        evaluationDate: data.evaluationDate,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evaluations'] });
      queryClient.invalidateQueries({ queryKey: ['allocation', allocationId] });
      toast.success('Recorded', {
        description: `This score now informs future rankings for ${allocation?.trainerRank} ${surname(
          allocation?.trainerName ?? '',
        )}.`,
      });
      navigate('/evaluations');
    },
    onError: () => toast.error('Could not record the evaluation. Please try again.'),
  });

  if (allocationQuery.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-80 rounded-md" />
      </div>
    );
  }
  if (allocationQuery.isError || !allocation) {
    return (
      <Card>
        <CardBody>
          <ErrorState onRetry={() => allocationQuery.refetch()} />
        </CardBody>
      </Card>
    );
  }

  const comments = form.watch('evaluatorComments');
  const canSubmit = conducted && comments.trim().length >= 20;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Evaluations"
        title="Record evaluation"
        description={allocation.programmeTitle}
        breadcrumbs={[{ label: 'Evaluations', to: '/evaluations' }, { label: 'Record' }]}
      />

      <Card className="max-w-form">
        <CardBody>
          <div className="mb-5">
            <KeyValueList
              items={[
                { label: 'Registry no.', value: allocation.registryNumber, mono: true },
                { label: 'Trainer', value: `${allocation.trainerRank} ${allocation.trainerName}` },
                { label: 'Programme', value: allocation.programmeTitle },
              ]}
            />
          </div>

          {!conducted && (
            <div className="mb-5 rounded-sm border border-warning-border bg-warning-bg px-3 py-2 text-body-sm text-warning-fg">
              This training has not been marked as conducted yet, so an evaluation cannot be
              recorded.
            </div>
          )}

          <form
            onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
            noValidate
            className="flex flex-col gap-5"
          >
            <FormField
              label="Score awarded"
              required
              error={form.formState.errors.scoreAwarded?.message}
              help="1.0 is the lowest, 5.0 the highest. Half steps are allowed."
            >
              <Controller
                control={form.control}
                name="scoreAwarded"
                render={({ field }) => (
                  <StarRatingInput value={field.value} onChange={field.onChange} disabled={!conducted} />
                )}
              />
            </FormField>

            <FormField
              label="Evaluator comments"
              required
              error={form.formState.errors.evaluatorComments?.message}
              help="At least 20 characters — this is what a reviewer reads months later."
            >
              <Textarea
                {...form.register('evaluatorComments')}
                placeholder="How did the trainer perform? What went well, what could improve?"
                maxLength={600}
                showCount
                disabled={!conducted}
              />
            </FormField>

            <FormField label="Evaluation date" required error={form.formState.errors.evaluationDate?.message}>
              <Controller
                control={form.control}
                name="evaluationDate"
                render={({ field }) => (
                  <DatePicker value={field.value} onChange={(v) => field.onChange(v ?? '')} disabled={!conducted} />
                )}
              />
            </FormField>

            <div className="flex items-center gap-3 border-t border-hairline pt-5">
              {canSubmit ? (
                <Button type="submit" loading={mutation.isPending}>
                  Record evaluation
                </Button>
              ) : (
                <Tooltip
                  content={
                    !conducted
                      ? 'Available once the training has been marked as conducted.'
                      : 'Write at least 20 characters of comments first.'
                  }
                  onDisabled
                >
                  <Button type="submit" disabled>
                    Record evaluation
                  </Button>
                </Tooltip>
              )}
              <Button type="button" variant="ghost" onClick={() => navigate('/evaluations')}>
                Cancel
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
