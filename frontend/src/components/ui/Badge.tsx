import { forwardRef } from 'react';
import { cn } from '@/lib/cn';
import type { SemanticTone } from '@/lib/constants';

/**
 * Badge — a 22px-tall pill (§5.3). `tone` maps to the semantic palette; the
 * neutral tone uses the sunken surface. Status is never colour-only — a tone
 * dot plus a text label always travel together (§4.1, §14.1).
 */
const toneClasses: Record<SemanticTone, string> = {
  success: 'bg-success-bg text-success-fg border-success-border',
  warning: 'bg-warning-bg text-warning-fg border-warning-border',
  danger: 'bg-danger-bg text-danger-fg border-danger-border',
  info: 'bg-info-bg text-info-fg border-info-border',
  neutral: 'bg-surface-sunken text-text-secondary border-hairline',
};

const dotColor: Record<SemanticTone, string> = {
  success: 'bg-success-fg',
  warning: 'bg-warning-fg',
  danger: 'bg-danger-fg',
  info: 'bg-info-fg',
  neutral: 'bg-text-muted',
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: SemanticTone;
  /** Show the leading tone dot (default true — carries meaning beyond colour). */
  dot?: boolean;
  /** Use mono uppercase label styling for identifiers/codes. */
  mono?: boolean;
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(function Badge(
  { className, tone = 'neutral', dot = true, mono = false, children, ...props },
  ref,
) {
  return (
    <span
      ref={ref}
      className={cn(
        'inline-flex h-badge shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2 align-middle leading-none',
        mono ? 'font-mono text-label uppercase tracking-[0.06em]' : 'text-caption font-medium',
        toneClasses[tone],
        className,
      )}
      {...props}
    >
      {dot && <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', dotColor[tone])} />}
      {children}
    </span>
  );
});
