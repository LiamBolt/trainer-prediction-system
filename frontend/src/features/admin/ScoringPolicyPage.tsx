import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, History, RotateCcw, Save } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  ErrorState,
  Skeleton,
  Slider,
  toast,
} from '@/components/ui';
import { ScoreLedgerLegend } from '@/components/prediction';
import { policyApi } from '@/api/endpoints';
import { useWeightStore } from '@/stores/weightStore';
import { CRITERIA, CRITERION_META, WEIGHT_PRESETS } from '@/lib/constants';
import { formatTimestamp } from '@/lib/format';
import type { CriterionKey, CriterionScore } from '@/types/domain';

/**
 * Scoring policy (NFR-10) — the saved policy weights, who last changed them and
 * when, the change history, and the Weight Studio in "save as policy" mode.
 * Saving writes an audit entry and warns that existing predictions will be
 * recalculated on their next run.
 */
export function ScoringPolicyPage() {
  const queryClient = useQueryClient();
  const { policy, setPolicy } = useWeightStore();
  const [draft, setDraft] = useState<Record<CriterionKey, number>>(policy);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const query = useQuery({ queryKey: ['scoring-policy'], queryFn: () => policyApi.getScoringPolicy() });

  useEffect(() => {
    if (query.data) {
      setDraft(query.data.weights);
      setPolicy(query.data.weights, false);
    }
  }, [query.data, setPolicy]);

  const save = useMutation({
    mutationFn: () => policyApi.saveScoringPolicy(draft),
    onSuccess: (record) => {
      setConfirmOpen(false);
      setPolicy(record.weights);
      queryClient.invalidateQueries({ queryKey: ['scoring-policy'] });
      toast.success('Scoring policy saved', {
        description: 'New predictions will use this weighting. An audit entry has been recorded.',
      });
    },
    onError: () => toast.error('Could not save the policy.'),
  });

  /** Proportional redistribution so the total is always 100. */
  const setWeight = (key: CriterionKey, value: number) => {
    const clamped = Math.max(0, Math.min(100, Math.round(value)));
    const others = CRITERIA.map((c) => c.key).filter((k) => k !== key);
    const remainder = 100 - clamped;
    const othersTotal = others.reduce((s, k) => s + draft[k], 0);
    const next = { ...draft, [key]: clamped };
    if (othersTotal === 0) {
      const each = Math.floor(remainder / others.length);
      others.forEach((k, i) => (next[k] = each + (i === 0 ? remainder - each * others.length : 0)));
    } else {
      others.forEach((k) => (next[k] = Math.round((draft[k] / othersTotal) * remainder)));
    }
    const drift = 100 - CRITERIA.reduce((s, c) => s + next[c.key], 0);
    if (drift !== 0) {
      const target = [...others].sort((a, b) => next[b] - next[a])[0] ?? key;
      next[target] = Math.max(0, next[target] + drift);
    }
    setDraft(next);
  };

  const dirty = CRITERIA.some((c) => draft[c.key] !== (query.data?.weights[c.key] ?? policy[c.key]));

  // Preview the weighting as a ledger legend (contribution === weight at 100%).
  const previewBreakdown: CriterionScore[] = CRITERIA.map((c) => ({
    key: c.key,
    label: c.label,
    weight: draft[c.key],
    rawValue: '',
    normalized: 100,
    contribution: draft[c.key],
    explanation: '',
    dataQuality: 'COMPLETE',
  }));

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-72" />
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

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Administration"
        title="Scoring policy"
        description="The force-wide weighting used for every prediction. Changing it is a policy decision, not a simulation."
      />

      <Card>
        <CardBody>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-body text-text-secondary">
              Last changed by{' '}
              <span className="font-semibold text-ink">{query.data.changedBy}</span>
            </span>
            <span className="font-mono text-data tabular-nums text-text-muted">
              {formatTimestamp(query.data.changedAt)}
            </span>
          </div>
        </CardBody>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <Card>
          <CardHeader>
            <CardTitle>Weighting</CardTitle>
            <p className="mt-1 text-body-sm text-text-muted">
              The five criteria always total 100. Adjusting one redistributes the remainder.
            </p>
          </CardHeader>
          <CardBody>
            <div className="flex flex-col gap-5">
              {CRITERIA.map((c) => (
                <div key={c.key} className="flex flex-col gap-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <label htmlFor={`policy-${c.key}`} className="text-body font-semibold text-ink">
                      {c.label}
                    </label>
                    <span className="font-mono text-data-lg tabular-nums text-ink">{draft[c.key]}</span>
                  </div>
                  <p className="text-body-sm text-text-muted">{c.description}</p>
                  <Slider
                    id={`policy-${c.key}`}
                    value={[draft[c.key]]}
                    onValueChange={([v]) => setWeight(c.key, v ?? 0)}
                    min={0}
                    max={100}
                    step={1}
                    aria-label={`${c.label} policy weight`}
                  />
                </div>
              ))}

              <div className="flex items-center justify-between rounded-sm border border-hairline bg-surface-sunken px-3 py-2">
                <span className="font-mono text-label uppercase text-text-muted">Total</span>
                <span className="font-mono text-data-lg font-semibold tabular-nums text-ink">100</span>
              </div>

              {dirty && (
                <div className="flex items-start gap-2 rounded-sm border border-warning-border bg-warning-bg px-3 py-2 text-body-sm text-warning-fg">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <span>
                    Saving changes the force-wide policy. Existing predictions keep their recorded
                    scores; new and re-run predictions will use this weighting.
                  </span>
                </div>
              )}

              <div className="flex flex-wrap items-center gap-3 border-t border-hairline pt-5">
                <Button onClick={() => setConfirmOpen(true)} disabled={!dirty} icon={<Save size={16} className="shrink-0" />}>
                  Save as policy
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setDraft(query.data.weights)}
                  disabled={!dirty}
                  icon={<RotateCcw size={16} className="shrink-0" />}
                >
                  Discard changes
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                {WEIGHT_PRESETS.map((p) => (
                  <Button key={p.id} variant="secondary" size="sm" onClick={() => setDraft(p.weights)}>
                    {p.label}
                  </Button>
                ))}
              </div>
            </div>
          </CardBody>
        </Card>

        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Weighting at a glance</CardTitle>
            </CardHeader>
            <CardBody>
              <ScoreLedgerLegend breakdown={previewBreakdown} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>
                <span className="flex items-center gap-2">
                  <History size={16} className="shrink-0 text-text-muted" />
                  Change history
                </span>
              </CardTitle>
            </CardHeader>
            <CardBody>
              <ul className="flex flex-col divide-y divide-hairline">
                {query.data.history.map((h, i) => (
                  <li key={i} className="flex flex-col gap-0.5 py-3">
                    <span className="text-body-sm text-ink">{h.note}</span>
                    <span className="font-mono text-label text-text-muted">
                      {h.changedBy} · {formatTimestamp(h.changedAt)}
                    </span>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Save this weighting as force policy?"
        description="This becomes the default weighting for every future prediction and is recorded in the audit log."
        confirmLabel="Save policy"
        loading={save.isPending}
        onConfirm={() => save.mutate()}
      >
        <ul className="flex flex-col gap-1">
          {CRITERIA.map((c) => (
            <li key={c.key} className="flex items-center justify-between text-body-sm">
              <span className="text-text-secondary">{CRITERION_META[c.key].label}</span>
              <span className="font-mono tabular-nums text-ink">{draft[c.key]}</span>
            </li>
          ))}
        </ul>
      </ConfirmDialog>
    </div>
  );
}
