import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import { Check, Minus } from 'lucide-react';
import { cn } from '@/lib/cn';

/** Checkbox — Radix, styled. 20px box aligns to body cap height (§5.3). */
export function Checkbox({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      className={cn(
        'flex h-5 w-5 shrink-0 items-center justify-center rounded-sm border border-strong bg-surface transition-colors duration-micro ' +
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
          'data-[state=checked]:border-brand data-[state=checked]:bg-brand data-[state=checked]:text-brand-fg ' +
          'data-[state=indeterminate]:border-brand data-[state=indeterminate]:bg-brand data-[state=indeterminate]:text-brand-fg ' +
          'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator>
        {props.checked === 'indeterminate' ? (
          <Minus size={14} strokeWidth={3} className="shrink-0" />
        ) : (
          <Check size={14} strokeWidth={3} className="shrink-0" />
        )}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}
