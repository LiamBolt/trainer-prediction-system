import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  Combobox,
  ErrorState,
  FormField,
  Input,
  NumberInput,
  Select,
  Skeleton,
  Tooltip,
  IconButton,
  toast,
} from '@/components/ui';
import { trainersApi } from '@/api/endpoints';
import { useAuth } from '@/hooks/useAuth';
import {
  INSTITUTIONS,
  PROFICIENCY_LABELS,
  PROFICIENCY_ORDER,
  QUALIFICATION_LABELS,
  QUALIFICATION_ORDER,
  SPECIALIZATIONS,
} from '@/lib/constants';
import type { QualificationLevel } from '@/types/domain';

interface QualRow {
  qualificationId: number;
  qualificationName: string;
  qualificationLevel: QualificationLevel | '';
  institutionName: string;
  yearObtained: number | '';
}
interface SpecRow {
  specializationId: number;
  specializationArea: string;
  proficiencyLevel: string;
}

/**
 * Qualifications and specialisations (FR-03). Two field arrays with clean
 * add/remove. Adding never overwrites an existing entry. A specialisation cannot
 * be saved without a proficiency level — the Save tooltip says so.
 */
export function MyQualificationsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [quals, setQuals] = useState<QualRow[]>([]);
  const [specs, setSpecs] = useState<SpecRow[]>([]);

  const query = useQuery({
    queryKey: ['me', 'trainer', user?.userId],
    queryFn: () => trainersApi.getMyTrainer(user!.userId),
    enabled: Boolean(user),
  });
  const trainer = query.data;

  useEffect(() => {
    if (!trainer) return;
    setQuals(
      trainer.qualifications.map((q) => ({
        qualificationId: q.qualificationId,
        qualificationName: q.qualificationName,
        qualificationLevel: q.qualificationLevel,
        institutionName: q.institutionName,
        yearObtained: q.yearObtained,
      })),
    );
    setSpecs(
      trainer.specializations.map((s) => ({
        specializationId: s.specializationId,
        specializationArea: s.specializationArea,
        proficiencyLevel: s.proficiencyLevel,
      })),
    );
  }, [trainer]);

  const mutation = useMutation({
    mutationFn: () =>
      trainersApi.updateTrainerCredentials(trainer!.trainerId, {
        qualifications: quals.map((q) => ({
          qualificationId: q.qualificationId,
          qualificationName: q.qualificationName,
          qualificationLevel: q.qualificationLevel as QualificationLevel,
          institutionName: q.institutionName,
          yearObtained: Number(q.yearObtained) || new Date().getFullYear(),
        })),
        specializations: specs.map((s) => ({
          specializationId: s.specializationId,
          specializationArea: s.specializationArea,
          proficiencyLevel: s.proficiencyLevel,
        })),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me', 'trainer'] });
      queryClient.invalidateQueries({ queryKey: ['trainers'] });
      toast.success('Saved', { description: 'Your credentials now inform future rankings.' });
    },
    onError: () => toast.error('Could not save. Please try again.'),
  });

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-64" />
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

  const specMissingProficiency = specs.some((s) => !s.proficiencyLevel || !s.specializationArea);
  const qualIncomplete = quals.some((q) => !q.qualificationLevel || !q.qualificationName);
  const blocked = specMissingProficiency || qualIncomplete;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Trainer"
        title="Qualifications and specialisations"
        description="These are the strongest signals in your ranking. Adding an entry never replaces an existing one."
        breadcrumbs={[{ label: 'My profile', to: '/my-profile' }, { label: 'Credentials' }]}
      />

      {/* Qualifications */}
      <Card>
        <CardHeader>
          <CardTitle>Qualifications</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col gap-5">
            {quals.length === 0 && (
              <p className="text-body-sm text-text-muted">No qualifications recorded yet.</p>
            )}
            {quals.map((q, i) => (
              <div key={q.qualificationId || `new-${i}`} className="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
                <FormField label="Qualification">
                  <Input
                    value={q.qualificationName}
                    onChange={(e) =>
                      setQuals((prev) => prev.map((r, j) => (j === i ? { ...r, qualificationName: e.target.value } : r)))
                    }
                    placeholder="e.g. BSc, Computer Science"
                  />
                </FormField>
                <FormField label="Level">
                  <Select
                    value={q.qualificationLevel || ''}
                    onValueChange={(v) =>
                      setQuals((prev) =>
                        prev.map((r, j) => (j === i ? { ...r, qualificationLevel: v as QualificationLevel } : r)),
                      )
                    }
                    options={QUALIFICATION_ORDER.map((l) => ({ value: l, label: QUALIFICATION_LABELS[l] }))}
                    placeholder="Choose a level"
                  />
                </FormField>
                <div className="flex items-end pb-1">
                  <IconButton
                    label="Remove qualification"
                    variant="ghost"
                    onClick={() => setQuals((prev) => prev.filter((_, j) => j !== i))}
                  >
                    <Trash2 size={16} className="shrink-0 text-danger-fg" />
                  </IconButton>
                </div>
                <FormField label="Institution" className="md:col-span-2">
                  <Combobox
                    value={q.institutionName}
                    onChange={(v) =>
                      setQuals((prev) => prev.map((r, j) => (j === i ? { ...r, institutionName: v } : r)))
                    }
                    options={INSTITUTIONS.map((n) => ({ value: n, label: n }))}
                    placeholder="Choose an institution"
                  />
                </FormField>
                <FormField label="Year">
                  <NumberInput
                    value={q.yearObtained}
                    onChange={(v) => setQuals((prev) => prev.map((r, j) => (j === i ? { ...r, yearObtained: v } : r)))}
                    min={1970}
                    max={2030}
                  />
                </FormField>
              </div>
            ))}
            <div>
              <Button
                variant="secondary"
                size="sm"
                icon={<Plus size={16} className="shrink-0" />}
                onClick={() =>
                  setQuals((prev) => [
                    ...prev,
                    { qualificationId: 0, qualificationName: '', qualificationLevel: '', institutionName: '', yearObtained: '' },
                  ])
                }
              >
                Add qualification
              </Button>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Specialisations */}
      <Card>
        <CardHeader>
          <CardTitle>Specialisations</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col gap-5">
            {specs.length === 0 && (
              <p className="text-body-sm text-text-muted">No specialisations recorded yet.</p>
            )}
            {specs.map((s, i) => (
              <div key={s.specializationId || `new-${i}`} className="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
                <FormField label="Specialisation area">
                  <Combobox
                    value={s.specializationArea}
                    onChange={(v) =>
                      setSpecs((prev) => prev.map((r, j) => (j === i ? { ...r, specializationArea: v } : r)))
                    }
                    options={SPECIALIZATIONS.map((n) => ({ value: n, label: n }))}
                    placeholder="Choose an area"
                  />
                </FormField>
                <FormField label="Proficiency" required>
                  <Select
                    value={s.proficiencyLevel}
                    onValueChange={(v) =>
                      setSpecs((prev) => prev.map((r, j) => (j === i ? { ...r, proficiencyLevel: v } : r)))
                    }
                    options={PROFICIENCY_ORDER.map((p) => ({ value: p, label: PROFICIENCY_LABELS[p] }))}
                    placeholder="Choose a level"
                  />
                </FormField>
                <div className="flex items-end pb-1">
                  <IconButton
                    label="Remove specialisation"
                    variant="ghost"
                    onClick={() => setSpecs((prev) => prev.filter((_, j) => j !== i))}
                  >
                    <Trash2 size={16} className="shrink-0 text-danger-fg" />
                  </IconButton>
                </div>
              </div>
            ))}
            <div>
              <Button
                variant="secondary"
                size="sm"
                icon={<Plus size={16} className="shrink-0" />}
                onClick={() =>
                  setSpecs((prev) => [...prev, { specializationId: 0, specializationArea: '', proficiencyLevel: '' }])
                }
              >
                Add specialisation
              </Button>
            </div>
          </div>
        </CardBody>
      </Card>

      <div className="flex items-center gap-3">
        {blocked ? (
          <Tooltip
            content={
              specMissingProficiency
                ? 'Every specialisation needs an area and a proficiency level before saving.'
                : 'Every qualification needs a name and a level before saving.'
            }
            onDisabled
          >
            <Button disabled>Save credentials</Button>
          </Tooltip>
        ) : (
          <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>
            Save credentials
          </Button>
        )}
      </div>
    </div>
  );
}
