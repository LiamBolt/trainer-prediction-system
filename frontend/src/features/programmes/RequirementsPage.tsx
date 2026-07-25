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
import { programmesApi, predictionsApi, referenceApi } from '@/api/endpoints';
import { formatCount } from '@/lib/format';
import { requirementsSchema, type RequirementsForm } from '@/schemas/programme';

/**
 * Define requirements (FR-05). The specialisation and minimum qualification come from
 * reference data and submit their numeric IDs (requiredSpecializationAreaId,
 * minimumQualificationLevelId). The eligibility preview reflects the SAVED
 * requirements — the API computes it server-side rather than from unsaved form values.
 */
export function RequirementsPage() {
  const { id } = useParams();
  const programmeId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const specializations = useQuery({ queryKey: ['ref', 'specializations'], queryFn: referenceApi.getSpecializations });
  const qualLevels = useQuery({ queryKey: ['ref', 'qualification-levels'], queryFn: referenceApi.getQualificationLevels });

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
      requiredSpecializationAreaId: programme?.requiredSpecializationAreaId
        ? String(programme.requiredSpecializationAreaId)
        : '',
      minimumExperience: programme?.minimumExperience ?? 0,
      minimumQualificationLevelId: programme?.minimumQualificationLevelId
        ? String(programme.minimumQualificationLevelId)
        : null,
    },
  });

  const watched = form.watch();

  // The API derives the preview from the SAVED requirements, so it is only meaningful
  // once they exist — enable it when the loaded programme already has a specialisation.
  const eligibility = useQuery({
    queryKey: ['eligibility', programmeId],
    queryFn: () => programmesApi.getEligibility(programmeId),
    enabled: Number.isFinite(programmeId) && Boolean(programme?.requiredSpecializationAreaId),
  });

  const saveMutation = useMutation({
    mutationFn: (data: RequirementsForm) =>
      programmesApi.setRequirements(programmeId, {
        requiredSpecializationAreaId: Number(data.requiredSpecializationAreaId),
        minimumExperience: Number(data.minimumExperience),
        minimumQualificationLevelId: data.minimumQualificationLevelId
          ? Number(data.minimumQualificationLevelId)
          : null,
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

  const blocked = !watched.requiredSpecializationAreaId;

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
                error={form.formState.errors.requiredSpecializationAreaId?.message}
                help="Only trainers holding this specialisation will be ranked (BR-04)."
              >
                <Controller
                  control={form.control}
                  name="requiredSpecializationAreaId"
                  render={({ field }) => (
                    <Combobox
                      value={field.value}
                      onChange={field.onChange}
                      options={(specializations.data ?? []).map((s) => ({
                        value: String(s.specializationAreaId),
                        label: s.name,
                      }))}
                      placeholder={specializations.isLoading ? 'Loading…' : 'Choose a specialisation'}
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
                  name="minimumQualificationLevelId"
                  render={({ field }) => (
                    <Select
                      value={field.value ?? 'any'}
                      onValueChange={(v) => field.onChange(v === 'any' ? null : v)}
                      options={[
                        { value: 'any', label: 'Any qualification' },
                        ...(qualLevels.data ?? []).map((q) => ({ value: String(q.levelId), label: q.name })),
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

        {/* Eligibility preview — reflects the saved requirements */}
        <Card className="lg:sticky lg:top-6">
          <CardBody>
            <div className="flex flex-col gap-3">
              <span className="flex items-center gap-2 font-mono text-label uppercase text-text-muted">
                <Users size={16} className="shrink-0" />
                Eligibility preview
              </span>
              {!programme?.requiredSpecializationAreaId ? (
                <p className="text-body-sm text-text-muted">
                  Save the requirements to see how many trainers currently qualify.
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
