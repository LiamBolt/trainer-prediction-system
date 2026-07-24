import { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Button,
  KeyValueList,
  FormField,
  Textarea,
} from '@/components/ui';
import { formatScore, ordinal } from '@/lib/format';
import type { Prediction, Trainer } from '@/types/domain';

/**
 * ApproveAllocationDialog — BR-06. Approval must be explicit and deliberate: the
 * dialog restates the trainer, programme, score, and rank. If simulated weights
 * are active, it warns that the allocation will record them.
 */
export function ApproveAllocationDialog({
  open,
  onOpenChange,
  programmeTitle,
  prediction,
  trainer,
  simulated,
  loading,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  programmeTitle: string;
  prediction: Prediction;
  trainer: Trainer;
  simulated: boolean;
  loading: boolean;
  onConfirm: (remarks: string) => void;
}) {
  const [remarks, setRemarks] = useState('');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>Approve this trainer</DialogTitle>
          <DialogDescription>
            This records a formal allocation and notifies the trainer. It cannot be undone without a
            new decision.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <div className="flex flex-col gap-4">
            <KeyValueList
              items={[
                { label: 'Trainer', value: `${trainer.policeRank} ${trainer.fullName}` },
                { label: 'Programme', value: programmeTitle },
                { label: 'Score', value: `${formatScore(prediction.predictionScore)} out of 100`, mono: true },
                { label: 'Rank', value: `${ordinal(prediction.rankPosition)} of the ranking`, mono: true },
              ]}
            />

            {simulated && (
              <div className="flex items-start gap-2 rounded-sm border border-warning-border bg-warning-bg px-3 py-2 text-body-sm text-warning-fg">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <span>
                  Simulated weights are active. This allocation will record the simulated weighting,
                  not the standard policy weighting.
                </span>
              </div>
            )}

            <FormField label="Remarks (optional)">
              <Textarea
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder="Add a note for the record…"
                maxLength={280}
                showCount
              />
            </FormField>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={() => onConfirm(remarks)} loading={loading}>
            Approve
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
