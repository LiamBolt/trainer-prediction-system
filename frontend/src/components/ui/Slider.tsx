import * as SliderPrimitive from '@radix-ui/react-slider';
import { cn } from '@/lib/cn';

/**
 * Slider — Radix. Arrow keys adjust, Home/End jump (§14.1). Drives the Weight
 * Studio (§12.6). Track uses the sunken surface; range + thumb use the brand.
 */
export function Slider({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>) {
  return (
    <SliderPrimitive.Root
      className={cn('relative flex w-full touch-none select-none items-center', className)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-2 w-full grow overflow-hidden rounded-full bg-surface-sunken">
        <SliderPrimitive.Range className="absolute h-full bg-brand" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        className={cn(
          'block h-5 w-5 rounded-full border-2 border-brand bg-surface shadow-e1 transition-colors',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
          'disabled:pointer-events-none disabled:opacity-50',
        )}
        aria-label="Weight"
      />
    </SliderPrimitive.Root>
  );
}
