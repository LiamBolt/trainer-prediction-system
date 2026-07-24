import * as RadioGroupPrimitive from '@radix-ui/react-radio-group';
import { cn } from '@/lib/cn';

export function RadioGroup({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Root>) {
  return <RadioGroupPrimitive.Root className={cn('flex flex-col gap-3', className)} {...props} />;
}

export function RadioGroupItem({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      className={cn(
        'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-strong bg-surface transition-colors duration-micro ' +
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
          'data-[state=checked]:border-brand disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <RadioGroupPrimitive.Indicator className="block h-2.5 w-2.5 rounded-full bg-brand" />
    </RadioGroupPrimitive.Item>
  );
}

/** Convenience row: radio + label + optional description. */
export function RadioOption({
  value,
  label,
  description,
  id,
}: {
  value: string;
  label: string;
  description?: string;
  id: string;
}) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-3">
      <RadioGroupItem value={value} id={id} className="mt-0.5" />
      <span className="flex flex-col">
        <span className="text-body font-medium text-ink">{label}</span>
        {description && <span className="text-body-sm text-text-muted">{description}</span>}
      </span>
    </label>
  );
}
