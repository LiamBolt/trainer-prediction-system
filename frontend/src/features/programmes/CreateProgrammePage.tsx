import { useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  DatePicker,
  FormField,
  Input,
  Select,
  Tooltip,
  toast,
} from '@/components/ui';
import { programmesApi, referenceApi } from '@/api/endpoints';
import { programmeCreateSchema, type ProgrammeCreateForm } from '@/schemas/programme';

/**
 * Create training request (FR-04). Category and location come from reference data and
 * submit their numeric IDs (categoryId, stationId) — the backend keys on those, not
 * on free-text names. On success the flow continues to the requirements step.
 */
export function CreateProgrammePage() {
  const navigate = useNavigate();
  const categories = useQuery({ queryKey: ['ref', 'categories'], queryFn: referenceApi.getCategories });
  const stations = useQuery({ queryKey: ['ref', 'stations'], queryFn: referenceApi.getStations });

  const form = useForm<ProgrammeCreateForm>({
    resolver: zodResolver(programmeCreateSchema),
    mode: 'onBlur',
    defaultValues: { title: '', categoryId: '', startDate: '', endDate: '', stationId: '' },
  });

  const values = form.watch();
  const missing: string[] = [];
  if (!values.categoryId) missing.push('a category');
  if (!values.startDate || !values.endDate) missing.push('both dates');
  if (!values.stationId) missing.push('a location');
  const blocked = missing.length > 0;

  const mutation = useMutation({
    mutationFn: (data: ProgrammeCreateForm) =>
      programmesApi.createProgramme({
        title: data.title,
        categoryId: Number(data.categoryId),
        startDate: data.startDate,
        endDate: data.endDate,
        stationId: Number(data.stationId),
      }),
    onSuccess: (programme) => {
      toast.success('Training request created', {
        description: 'Next, define the requirements so trainers can be matched.',
      });
      navigate(`/programmes/${programme.programmeId}/requirements`);
    },
    onError: () => toast.error('Could not create the request. Please try again.'),
  });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Programmes"
        title="Create training request"
        description="Record the course to be delivered. You will define the trainer requirements next."
        breadcrumbs={[{ label: 'Training requests', to: '/programmes' }, { label: 'New request' }]}
      />

      <Card className="max-w-form">
        <CardBody>
          <form
            onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
            noValidate
            className="flex flex-col gap-5"
          >
            <FormField label="Course title" required error={form.formState.errors.title?.message}>
              <Input
                {...form.register('title')}
                placeholder="e.g. Basic Cybercrime Investigation Course — Intake 15"
              />
            </FormField>

            <FormField label="Category" required error={form.formState.errors.categoryId?.message}>
              <Controller
                control={form.control}
                name="categoryId"
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    options={(categories.data ?? []).map((c) => ({ value: String(c.categoryId), label: c.name }))}
                    placeholder={categories.isLoading ? 'Loading…' : 'Choose a category'}
                  />
                )}
              />
            </FormField>

            <div className="grid gap-5 sm:grid-cols-2">
              <FormField label="Start date" required error={form.formState.errors.startDate?.message}>
                <Controller
                  control={form.control}
                  name="startDate"
                  render={({ field }) => (
                    <DatePicker value={field.value} onChange={(v) => field.onChange(v ?? '')} />
                  )}
                />
              </FormField>
              <FormField label="End date" required error={form.formState.errors.endDate?.message}>
                <Controller
                  control={form.control}
                  name="endDate"
                  render={({ field }) => (
                    <DatePicker
                      value={field.value}
                      onChange={(v) => field.onChange(v ?? '')}
                      minDate={values.startDate || undefined}
                    />
                  )}
                />
              </FormField>
            </div>

            <FormField label="Location" required error={form.formState.errors.stationId?.message}>
              <Controller
                control={form.control}
                name="stationId"
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    options={(stations.data ?? []).map((s) => ({ value: String(s.stationId), label: s.name }))}
                    placeholder={stations.isLoading ? 'Loading…' : 'Choose a location'}
                  />
                )}
              />
            </FormField>

            <div className="flex items-center gap-3 border-t border-hairline pt-5">
              {blocked ? (
                <Tooltip content={`Add ${missing.join(', ')} before submitting.`} onDisabled>
                  <Button type="submit" disabled>
                    Create request
                  </Button>
                </Tooltip>
              ) : (
                <Button type="submit" loading={mutation.isPending}>
                  Create request
                </Button>
              )}
              <Button type="button" variant="ghost" onClick={() => navigate('/programmes')}>
                Cancel
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
