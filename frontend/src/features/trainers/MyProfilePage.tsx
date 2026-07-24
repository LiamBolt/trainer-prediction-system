import { Link } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  ErrorState,
  FormField,
  NumberInput,
  PhoneInput,
  Progress,
  Select,
  Skeleton,
  Switch,
  Tooltip,
  toast,
} from '@/components/ui';
import { trainersApi } from '@/api/endpoints';
import { useAuth } from '@/hooks/useAuth';
import { RANK_FULL_NAMES, STATIONS, TRAINER_RANKS } from '@/lib/constants';
import { trainerProfileSchema, type TrainerProfileForm } from '@/schemas/trainer';
import type { AvailabilityStatus, PoliceRank } from '@/types/domain';

/**
 * My profile (FR-02). Editable rank, station, years of service, contact number,
 * and availability. Rank, station, and contact number cannot be saved blank —
 * the disabled Save tooltip names what is missing.
 */
export function MyProfilePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['me', 'trainer', user?.userId],
    queryFn: () => trainersApi.getMyTrainer(user!.userId),
    enabled: Boolean(user),
  });
  const trainer = query.data;

  const form = useForm<TrainerProfileForm>({
    resolver: zodResolver(trainerProfileSchema),
    mode: 'onBlur',
    values: {
      policeRank: trainer?.policeRank ?? '',
      station: trainer?.station ?? '',
      yearsExperience: trainer?.yearsExperience ?? 0,
      contactNumber: trainer?.contactNumber ?? '',
      availabilityStatus: trainer?.availabilityStatus ?? 'AVAILABLE',
    },
  });

  const mutation = useMutation({
    mutationFn: (data: TrainerProfileForm) =>
      trainersApi.updateTrainer(trainer!.trainerId, {
        policeRank: data.policeRank as PoliceRank,
        station: data.station,
        yearsExperience: Number(data.yearsExperience),
        contactNumber: data.contactNumber,
        availabilityStatus: data.availabilityStatus as AvailabilityStatus,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me', 'trainer'] });
      queryClient.invalidateQueries({ queryKey: ['trainers'] });
      toast.success('Profile saved');
    },
    onError: () => toast.error('Could not save your profile. Please try again.'),
  });

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 rounded-md" />
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

  const v = form.watch();
  const missing: string[] = [];
  if (!v.policeRank) missing.push('rank');
  if (!v.station) missing.push('station');
  if (!v.contactNumber || v.contactNumber.length < 13) missing.push('contact number');
  const blocked = missing.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Trainer"
        title="My profile"
        description="Keep these details current — they feed directly into how you are ranked for courses."
        actions={
          <Button asChild variant="secondary">
            <Link to="/my-profile/qualifications">Qualifications and specialisations</Link>
          </Button>
        }
      />

      <Card>
        <CardBody>
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-label uppercase text-text-muted">Profile completeness</span>
              <span className="font-mono text-data tabular-nums text-ink">{trainer.profileCompleteness}%</span>
            </div>
            <Progress value={trainer.profileCompleteness} />
            <p className="text-body-sm text-text-muted">
              A fuller profile raises the confidence the system has in your ranking.
            </p>
          </div>
        </CardBody>
      </Card>

      <Card className="max-w-form">
        <CardBody>
          <form
            onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
            noValidate
            className="flex flex-col gap-5"
          >
            <FormField label="Rank" required error={form.formState.errors.policeRank?.message}>
              <Controller
                control={form.control}
                name="policeRank"
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    options={TRAINER_RANKS.map((r) => ({ value: r, label: `${r} — ${RANK_FULL_NAMES[r]}` }))}
                    placeholder="Choose your rank"
                  />
                )}
              />
            </FormField>

            <FormField label="Station" required error={form.formState.errors.station?.message}>
              <Controller
                control={form.control}
                name="station"
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    options={STATIONS.map((s) => ({ value: s.name, label: s.name }))}
                    placeholder="Choose your station"
                  />
                )}
              />
            </FormField>

            <FormField label="Years of service" error={form.formState.errors.yearsExperience?.message}>
              <Controller
                control={form.control}
                name="yearsExperience"
                render={({ field }) => (
                  <NumberInput
                    value={field.value === undefined ? '' : Number(field.value)}
                    onChange={(val) => field.onChange(val === '' ? 0 : val)}
                    min={0}
                    max={45}
                    suffix="years"
                  />
                )}
              />
            </FormField>

            <FormField label="Contact number" required error={form.formState.errors.contactNumber?.message}>
              <Controller
                control={form.control}
                name="contactNumber"
                render={({ field }) => <PhoneInput value={field.value} onChange={field.onChange} />}
              />
            </FormField>

            <FormField
              label="Availability"
              help="Marking yourself unavailable removes you from new rankings (BR-03)."
            >
              <Controller
                control={form.control}
                name="availabilityStatus"
                render={({ field }) => (
                  <label className="flex items-center gap-3">
                    <Switch
                      checked={field.value !== 'UNAVAILABLE'}
                      onCheckedChange={(checked) => field.onChange(checked ? 'AVAILABLE' : 'UNAVAILABLE')}
                    />
                    <span className="text-body text-ink">
                      {field.value === 'UNAVAILABLE'
                        ? 'Unavailable for new assignments'
                        : 'Available for new assignments'}
                    </span>
                  </label>
                )}
              />
            </FormField>

            <div className="flex items-center gap-3 border-t border-hairline pt-5">
              {blocked ? (
                <Tooltip content={`Add your ${missing.join(', ')} before saving.`} onDisabled>
                  <Button type="submit" disabled>
                    Save profile
                  </Button>
                </Tooltip>
              ) : (
                <Button type="submit" loading={mutation.isPending}>
                  Save profile
                </Button>
              )}
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
