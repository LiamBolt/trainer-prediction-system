import { Building2 } from 'lucide-react';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Button,
} from '@/components/ui';
import { ORG_UNIT } from '@/lib/constants';

/**
 * NeedAccessDialog — D3. Accounts are created by the System Administrator; this
 * is an instruction, NOT a form. No email field, no submit that creates access.
 */
export function NeedAccessDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm">
        <DialogHeader>
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-surface-sunken text-brand">
            <Building2 size={20} className="shrink-0" />
          </div>
          <DialogTitle>Need access?</DialogTitle>
          <DialogDescription>
            Accounts for the Trainer Prediction System are created by your System Administrator.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <p className="text-body text-text-secondary">
            Contact {ORG_UNIT} to request an account. You will be given a username and an initial
            password to sign in with.
          </p>
        </DialogBody>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Understood</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
