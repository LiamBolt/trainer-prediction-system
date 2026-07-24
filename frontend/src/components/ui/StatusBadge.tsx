import { Badge, type BadgeProps } from './Badge';
import {
  ACCOUNT_STATUS_LABELS,
  ACCOUNT_STATUS_TONE,
  ALLOCATION_STATUS_LABELS,
  ALLOCATION_STATUS_TONE,
  AVAILABILITY_LABELS,
  AVAILABILITY_TONE,
  CONFIDENCE_LABELS,
  CONFIDENCE_TONE,
  PROGRAMME_STATUS_LABELS,
  PROGRAMME_STATUS_TONE,
} from '@/lib/constants';
import type {
  AccountStatus,
  AllocationStatus,
  AvailabilityStatus,
  ConfidenceBand,
  ProgrammeStatus,
} from '@/types/domain';

/**
 * StatusBadge — maps every status enum in §6 to a semantic colour AND a label.
 * A discriminated `kind` keeps each mapping type-safe. Colour never travels
 * without its label (§4.1).
 */
type StatusBadgeProps = { className?: string; dot?: BadgeProps['dot'] } & (
  | { kind: 'programme'; value: ProgrammeStatus }
  | { kind: 'allocation'; value: AllocationStatus }
  | { kind: 'availability'; value: AvailabilityStatus }
  | { kind: 'account'; value: AccountStatus }
  | { kind: 'confidence'; value: ConfidenceBand }
);

export function StatusBadge(props: StatusBadgeProps) {
  const { className, dot } = props;
  switch (props.kind) {
    case 'programme':
      return (
        <Badge tone={PROGRAMME_STATUS_TONE[props.value]} dot={dot} className={className}>
          {PROGRAMME_STATUS_LABELS[props.value]}
        </Badge>
      );
    case 'allocation':
      return (
        <Badge tone={ALLOCATION_STATUS_TONE[props.value]} dot={dot} className={className}>
          {ALLOCATION_STATUS_LABELS[props.value]}
        </Badge>
      );
    case 'availability':
      return (
        <Badge tone={AVAILABILITY_TONE[props.value]} dot={dot} className={className}>
          {AVAILABILITY_LABELS[props.value]}
        </Badge>
      );
    case 'account':
      return (
        <Badge tone={ACCOUNT_STATUS_TONE[props.value]} dot={dot} className={className}>
          {ACCOUNT_STATUS_LABELS[props.value]}
        </Badge>
      );
    case 'confidence':
      return (
        <Badge tone={CONFIDENCE_TONE[props.value]} dot={dot} className={className}>
          {CONFIDENCE_LABELS[props.value]} confidence
        </Badge>
      );
  }
}
