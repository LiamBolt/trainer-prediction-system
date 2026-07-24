import * as PopoverPrimitive from '@radix-ui/react-popover';
import { cn } from '@/lib/cn';

/** Popover — floating panel, glass allowed only for notifications/user menu (§4.5). */
export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;
export const PopoverClose = PopoverPrimitive.Close;

export function PopoverContent({
  className,
  align = 'center',
  sideOffset = 6,
  glass = false,
  ...props
}: React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content> & { glass?: boolean }) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-50 rounded-md shadow-e3 outline-none',
          glass ? 'glass' : 'border border-hairline bg-surface',
          'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 duration-panel',
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}
