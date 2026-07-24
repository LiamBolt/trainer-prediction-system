import { StatusBadge } from '@/components/ui';
import type { AvailabilityStatus } from '@/types/domain';

/** AvailabilityPill — a thin StatusBadge wrapper for a trainer's availability. */
export function AvailabilityPill({ status }: { status: AvailabilityStatus }) {
  return <StatusBadge kind="availability" value={status} />;
}
