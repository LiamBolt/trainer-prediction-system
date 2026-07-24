import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { motion, MotionConfig } from 'framer-motion';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Card,
  CardBody,
  Spinner,
  ErrorState,
  EmptyState,
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  toast,
} from '@/components/ui';
import {
  ExclusionLedger,
  PredictionRunHeader,
  RankedTrainerRow,
  WeightStudio,
} from '@/components/prediction';
import { TrainerDetailRail } from './TrainerDetailRail';
import { ApproveAllocationDialog } from './ApproveAllocationDialog';
import { predictionsApi, programmesApi, allocationsApi, trainersApi } from '@/api/endpoints';
import { useAuth } from '@/hooks/useAuth';
import { useUiStore } from '@/stores/uiStore';
import { useWeightStore } from '@/stores/weightStore';
import { useDebounce } from '@/hooks/useDebounce';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { rerank } from '@/lib/rerank';
import { surname } from '@/lib/format';
import type { Trainer } from '@/types/domain';

const DISPLAY_LIMIT = 40;

export function PredictionPage() {
  const { id } = useParams();
  const programmeId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { role } = useAuth();
  const isAdmin = role === 'TRAINING_ADMINISTRATOR';
  const isDesktop = useMediaQuery('(min-width: 1280px)');
  const reduceMotionPref = useUiStore((s) => s.reduceMotion);

  const { weights, simulated, resetToPolicy } = useWeightStore();
  const debouncedWeights = useDebounce(weights, 120);

  const [selectedTrainerId, setSelectedTrainerId] = useState<number | null>(null);
  const [studioOpen, setStudioOpen] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [approveOpen, setApproveOpen] = useState(false);
  const [announce, setAnnounce] = useState('');

  const programmeQuery = useQuery({
    queryKey: ['programme', programmeId],
    queryFn: () => programmesApi.getProgramme(programmeId),
    enabled: Number.isFinite(programmeId),
  });
  const runQuery = useQuery({
    queryKey: ['prediction', programmeId],
    queryFn: () => predictionsApi.getPrediction(programmeId),
    enabled: Number.isFinite(programmeId),
    staleTime: 0,
  });
  const trainersQuery = useQuery({
    queryKey: ['trainers', 'all'],
    queryFn: () => trainersApi.listTrainers({ pageSize: 1000 }),
    staleTime: 60_000,
  });

  const trainerMap = useMemo(() => {
    const map = new Map<number, Trainer>();
    trainersQuery.data?.items.forEach((t) => map.set(t.trainerId, t));
    return map;
  }, [trainersQuery.data]);

  const run = runQuery.data;
  const reranked = useMemo(() => {
    if (!run) return null;
    return rerank(run.predictions, debouncedWeights, trainerMap);
  }, [run, debouncedWeights, trainerMap]);

  // Announce re-rank consequences politely (§14.1).
  useEffect(() => {
    if (reranked && simulated) {
      setAnnounce(`Ranking updated. ${reranked.changedCount} positions changed.`);
    }
  }, [reranked, simulated]);

  const rankedList = reranked?.ranked ?? [];
  const effectiveSelectedId = selectedTrainerId ?? rankedList[0]?.trainerId ?? null;
  const selectedPrediction = rankedList.find((p) => p.trainerId === effectiveSelectedId);
  const selectedTrainer = effectiveSelectedId ? trainerMap.get(effectiveSelectedId) : undefined;

  // Reset selection when navigating to a different programme.
  useEffect(() => {
    setSelectedTrainerId(null);
  }, [programmeId]);

  const rerunMutation = useMutation({
    mutationFn: () => predictionsApi.generatePrediction(programmeId),
    onSuccess: (fresh) => {
      resetToPolicy();
      queryClient.setQueryData(['prediction', programmeId], fresh);
      toast.success('Prediction re-run', {
        description: `Ranked ${fresh.rankedCount} trainers in ${(fresh.elapsedMs / 1000).toFixed(1)}s.`,
      });
    },
    onError: () => toast.error('Could not re-run the prediction. Please try again.'),
  });

  const approveMutation = useMutation({
    mutationFn: (remarks: string) =>
      allocationsApi.approveAllocation({
        predictionId: selectedPrediction!.predictionId,
        programmeId,
        trainerId: selectedPrediction!.trainerId,
        remarks,
        weights: debouncedWeights,
        weightsWereSimulated: simulated,
      }),
    onSuccess: (allocation) => {
      setApproveOpen(false);
      queryClient.invalidateQueries({ queryKey: ['programme', programmeId] });
      queryClient.invalidateQueries({ queryKey: ['allocations'] });
      toast.success('Approved', {
        description: `${allocation.registryNumber} recorded. The trainer has been notified.`,
      });
      navigate(`/allocations/${allocation.allocationId}`);
    },
    onError: () => toast.error('Could not record the allocation. Please try again.'),
  });

  const select = (trainerId: number) => {
    setSelectedTrainerId(trainerId);
    if (!isDesktop) setRailOpen(true);
  };
  const skipToNext = () => {
    if (!selectedPrediction) return;
    const next = rankedList.find((p) => p.rankPosition === selectedPrediction.rankPosition + 1);
    if (next) setSelectedTrainerId(next.trainerId);
  };

  const studioSummary = useMemo(() => {
    if (!reranked || !simulated || !run) return null;
    if (reranked.changedCount === 0) return <>No rankings changed at this weighting.</>;
    const fromT = reranked.topFromTrainerId ? trainerMap.get(reranked.topFromTrainerId) : undefined;
    const toT = reranked.topToTrainerId ? trainerMap.get(reranked.topToTrainerId) : undefined;
    const topChanged = reranked.topFromTrainerId !== reranked.topToTrainerId && fromT && toT;
    return (
      <>
        {reranked.changedCount} of {run.rankedCount} rankings changed.
        {topChanged && (
          <>
            {' '}
            The top-ranked trainer changed from{' '}
            <span className="font-semibold">
              {fromT.policeRank} {surname(fromT.fullName)}
            </span>{' '}
            to{' '}
            <span className="font-semibold">
              {toT.policeRank} {surname(toT.fullName)}
            </span>
            .
          </>
        )}
      </>
    );
  }, [reranked, simulated, run, trainerMap]);

  // --- states ---
  if (programmeQuery.isError || runQuery.isError) {
    return (
      <Card>
        <CardBody>
          <ErrorState onRetry={() => { void runQuery.refetch(); void programmeQuery.refetch(); }} />
        </CardBody>
      </Card>
    );
  }
  if (runQuery.isLoading || trainersQuery.isLoading || !run || !reranked) {
    return (
      <div className="flex min-h-panel flex-col items-center justify-center gap-4">
        <Spinner size={48} />
        <p className="text-body text-text-muted">Ranking the eligible trainers…</p>
      </div>
    );
  }
  if (run.rankedCount === 0) {
    return (
      <Card>
        <CardBody>
          <EmptyState
            title="No eligible trainers"
            description="Every trainer was excluded by the current requirements. Review the requirements or the exclusion ledger below."
          />
        </CardBody>
      </Card>
    );
  }

  const displayed = rankedList.slice(0, DISPLAY_LIMIT);
  const programmeTitle = programmeQuery.data?.programme.title ?? 'Prediction';

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Decision support · Prediction"
        title={programmeTitle}
        breadcrumbs={[
          { label: 'Training requests', to: '/programmes' },
          { label: programmeTitle, to: `/programmes/${programmeId}` },
          { label: 'Prediction' },
        ]}
      />

      <PredictionRunHeader
        run={run}
        simulated={simulated}
        onRerun={() => rerunMutation.mutate()}
        rerunning={rerunMutation.isPending}
        onOpenStudio={() => setStudioOpen(true)}
        canTune={isAdmin}
      />

      <div className="xl:grid xl:grid-cols-predict xl:items-start xl:gap-6">
        {/* Ranked list */}
        <div className="flex flex-col gap-3">
          <span aria-live="polite" className="sr-only">
            {announce}
          </span>
          <MotionConfig reducedMotion={reduceMotionPref ? 'always' : 'user'}>
            <div className="flex flex-col gap-3">
              {displayed.map((p) => {
                const trainer = trainerMap.get(p.trainerId);
                if (!trainer) return null;
                return (
                  <motion.div
                    key={p.trainerId}
                    layout
                    transition={{ duration: 0.32, ease: [0.2, 0.8, 0.2, 1] }}
                  >
                    <RankedTrainerRow
                      prediction={p}
                      trainer={trainer}
                      selected={p.trainerId === effectiveSelectedId}
                      onSelect={() => select(p.trainerId)}
                      delta={reranked.deltaByTrainer[p.trainerId] ?? 0}
                    />
                  </motion.div>
                );
              })}
            </div>
          </MotionConfig>
          {rankedList.length > DISPLAY_LIMIT && (
            <p className="py-2 text-center text-body-sm text-text-muted">
              Showing the top {DISPLAY_LIMIT} of {run.rankedCount} ranked trainers.
            </p>
          )}
        </div>

        {/* Detail rail (desktop) */}
        {isDesktop && selectedPrediction && selectedTrainer && (
          <aside className="xl:sticky xl:top-6">
            <Card>
              <CardBody>
                <TrainerDetailRail
                  prediction={selectedPrediction}
                  trainer={selectedTrainer}
                  isAdmin={isAdmin}
                  canSkip={selectedPrediction.rankPosition < rankedList.length}
                  onApprove={() => setApproveOpen(true)}
                  onSkip={skipToNext}
                />
              </CardBody>
            </Card>
          </aside>
        )}
      </div>

      <ExclusionLedger run={run} />

      {isAdmin && (
        <WeightStudio open={studioOpen} onOpenChange={setStudioOpen} summary={studioSummary} />
      )}

      {/* Detail rail (mobile drawer) */}
      {!isDesktop && (
        <Drawer open={railOpen} onOpenChange={setRailOpen}>
          <DrawerContent width="lg">
            <DrawerHeader>
              <DrawerTitle>Candidate detail</DrawerTitle>
            </DrawerHeader>
            <DrawerBody>
              {selectedPrediction && selectedTrainer && (
                <TrainerDetailRail
                  prediction={selectedPrediction}
                  trainer={selectedTrainer}
                  isAdmin={isAdmin}
                  canSkip={selectedPrediction.rankPosition < rankedList.length}
                  onApprove={() => setApproveOpen(true)}
                  onSkip={skipToNext}
                />
              )}
            </DrawerBody>
          </DrawerContent>
        </Drawer>
      )}

      {selectedPrediction && selectedTrainer && (
        <ApproveAllocationDialog
          open={approveOpen}
          onOpenChange={setApproveOpen}
          programmeTitle={programmeTitle}
          prediction={selectedPrediction}
          trainer={selectedTrainer}
          simulated={simulated}
          loading={approveMutation.isPending}
          onConfirm={(remarks) => approveMutation.mutate(remarks)}
        />
      )}
    </div>
  );
}
