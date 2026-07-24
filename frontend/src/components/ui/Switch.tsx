import * as SwitchPrimitive from '@radix-ui/react-switch';
import { cn } from '@/lib/cn';

/** Switch — Radix toggle. Used for availability, theme, plain-language, etc. */
export function Switch({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        'peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-micro ' +
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
          'data-[state=checked]:bg-brand data-[state=unchecked]:bg-primary-300 dark:data-[state=unchecked]:bg-primary-600 ' +
          'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="pointer-events-none block h-5 w-5 rounded-full bg-primary-50 shadow-e1 ring-0 transition-transform duration-micro data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0" />
    </SwitchPrimitive.Root>
  );
}
