import * as ProgressPrimitive from '@radix-ui/react-progress';
import { cn } from '@/lib/cn';

/** Progress — a plain determinate meter (NOT the Score Ledger, which is bespoke). */
export function Progress({
  value = 0,
  className,
  barClassName,
  ...props
}: React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & {
  value?: number;
  barClassName?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <ProgressPrimitive.Root
      value={clamped}
      className={cn('relative h-2 w-full overflow-hidden rounded-full bg-surface-sunken', className)}
      {...props}
    >
      <ProgressPrimitive.Indicator
        className={cn('h-full rounded-full bg-brand transition-transform duration-panel ease-entry', barClassName)}
        style={{ transform: `translateX(-${100 - clamped}%)` }}
      />
    </ProgressPrimitive.Root>
  );
}
