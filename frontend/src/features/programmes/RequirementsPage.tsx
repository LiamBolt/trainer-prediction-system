import { useNavigate, useParams } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Users } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  Combobox,
  FormField,
  NumberInput,
  Select,
  Tooltip,
  DotPulse,
  toast,
} from '@/components/ui';
import { programmesApi, predictionsApi } from '@/api/endpoints';
import { useDebounce } from '@/hooks/useDebounce';
import { QUALIFICATION_LABELS, QUALIFICATION_ORDER, SPECIALIZATIONS } from '@/lib/constants';
import { formatCount } from '@/lib/format';
import { requirementsSchema, type RequirementsForm } from '@/schemas/programme';
import type { QualificationLevel } from '@/types/domain';

/**
 * Define requirements (FR-05). A live eligibility preview shows how many trainers
 * currently meet the criteria and updates as fields change — the moment an Officer
 * learns their requirements are too narrow, BEFORE wasting a prediction run.
 */
export function RequirementsPage() {
  const { id } = useParams();
  const programmeId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const programmeQuery = useQuery({
    queryKey: ['programme', programmeId],
    queryFn: () => programmesApi.getProgramme(programmeId),
    enabled: Number.isFinite(programmeId),
  });
  const programme = programmeQuery.data?.programme;

  const form = useForm<RequirementsForm>({
    resolver: zodResolver(requirementsSchema),
    mode: 'onBlur',
    values: {
      requiredSpecialization: programme?.requiredSpecialization ?? '',
      minimumExperience: programme?.minimumExperience ?? 0,
      minimumQualification: programme?.minimumQualification ?? null,
    },
  });

  const watched = form.watch();
  const debounced = useDebounce(watched, 300);

  const eligibility = useQuery({
    queryKey: ['eligibility', programmeId, debounced],
    queryFn: () =>
      programmesApi.getEligibility(programmeId, {
        specialization: debounced.requiredSpecialization,
        minExp: Number(debounced.minimumExperience) || 0,
        minQual: debounced.minimumQualification,
      }),
    enabled: Number.isFinite(programmeId) && Boolean(debounced.requiredSpecialization),
  });

  const saveMutation = useMutation({
    mutationFn: (data: RequirementsForm) =>
      programmesApi.setRequirements(programmeId, {
        requiredSpecialization: data.requiredSpecialization,
        minimumExperience: Number(data.minimumExperience),
        minimumQualification: (data.minimumQualification || null) as QualificationLevel | null,
      }),
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ['programme', programmeId] });
      toast.success('Requirements saved');
      await predictionsApi.generatePrediction(programmeId);
      queryClient.invalidateQueries({ queryKey: ['prediction', programmeId] });
      navigate(`/programmes/${programmeId}/prediction`);
    },
    onError: () => toast.error('Could not save the requirements. Please try again.'),
  });

  const blocked = !watched.requiredSpecialization;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Programmes"
        title="Define requirements"
        description={programme?.title ?? 'Set what this course requires of a trainer.'}
        breadcrumbs={[
          { label: 'Training requests', to: '/programmes' },
          { label: programme?.title ?? 'Request', to: `/programmes/${programmeId}` },
          { label: 'Requirements' },
        ]}
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <Card className="max-w-form">
          <CardBody>
            <form
              onSubmit={form.handleSubmit((data) => saveMutation.mutate(data))}
              noValidate
              className="flex flex-col gap-5"
            >
              <FormField
                label="Required specialisation"
                required
                error={form.formState.errors.requiredSpecialization?.message}
                help="Only trainers holding this specialisation will be ranked (BR-04)."
              >
                <Controller
                  control={form.control}
                  name="requiredSpecialization"
                  render={({ field }) => (
                    <Combobox
                      value={field.value}
                      onChange={field.onChange}
                      options={SPECIALIZATIONS.map((s) => ({ value: s, label: s }))}
                      placeholder="Choose a specialisation"
                      searchPlaceholder="Search specialisations…"
                    />
                  )}
                />
              </FormField>

              <FormField
                label="Minimum years of experience"
                error={form.formState.errors.minimumExperience?.message}
              >
                <Controller
                  control={form.control}
                  name="minimumExperience"
                  render={({ field }) => (
                    <NumberInput
                      value={field.value === undefined ? '' : Number(field.value)}
                      onChange={(v) => field.onChange(v === '' ? 0 : v)}
                      min={0}
                      max={40}
                      suffix="years"
                    />
                  )}
                />
              </FormField>

              <FormField label="Minimum qualification (optional)">
                <Controller
                  control={form.control}
                  name="minimumQualification"
                  render={({ field }) => (
                    <Select
                      value={field.value ?? 'any'}
                      onValueChange={(v) => field.onChange(v === 'any' ? null : v)}
                      options={[
                        { value: 'any', label: 'Any qualification' },
                        ...QUALIFICATION_ORDER.map((q) => ({ value: q, label: QUALIFICATION_LABELS[q] })),
                      ]}
                    />
                  )}
                />
              </FormField>

              <div className="flex items-center gap-3 border-t border-hairline pt-5">
                {blocked ? (
                  <Tooltip content="Choose the required specialisation before running a prediction." onDisabled>
                    <Button type="submit" disabled>
                      Save and run prediction
                    </Button>
                  </Tooltip>
                ) : (
                  <Button type="submit" loading={saveMutation.isPending}>
                    Save and run prediction
                  </Button>
                )}
                <Button type="button" variant="ghost" onClick={() => navigate(`/programmes/${programmeId}`)}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>

        {/* Live eligibility preview */}
        <Card className="lg:sticky lg:top-6">
          <CardBody>
            <div className="flex flex-col gap-3">
              <span className="flex items-center gap-2 font-mono text-label uppercase text-text-muted">
                <Users size={16} className="shrink-0" />
                Eligibility preview
              </span>
              {!watched.requiredSpecialization ? (
                <p className="text-body-sm text-text-muted">
                  Choose a specialisation to see how many trainers currently qualify.
                </p>
              ) : eligibility.isFetching ? (
                <div className="flex items-center gap-2 text-text-muted">
                  <DotPulse size={16} />
                  <span className="text-body-sm">Checking…</span>
                </div>
              ) : eligibility.data ? (
                <>
                  <p className="text-body-lg text-ink">
                    <span className="font-mono text-data-xl tabular-nums">
                      {formatCount(eligibility.data.eligible)}
                    </span>{' '}
                    of {formatCount(eligibility.data.total)} trainers currently meet these criteria.
                  </p>
                  {eligibility.data.eligible === 0 && (
                    <p className="rounded-sm border border-warning-border bg-warning-bg px-3 py-2 text-body-sm text-warning-fg">
                      No trainer qualifies. Relax the experience or qualification minimum, or choose a
                      different specialisation.
                    </p>
                  )}
                  {eligibility.data.eligible > 0 && eligibility.data.eligible < 5 && (
                    <p className="rounded-sm border border-warning-border bg-warning-bg px-3 py-2 text-body-sm text-warning-fg">
                      Very few trainers qualify. Consider widening the requirements.
                    </p>
                  )}
                </>
              ) : null}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
