import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * Drawer — a side sheet built on Radix Dialog (focus trap, escape, return focus).
 * Used for the Weight Studio, the mobile sidebar, and the prediction detail rail
 * below 1280px. Glass overlay (§4.5).
 */
export const Drawer = DialogPrimitive.Root;
export const DrawerTrigger = DialogPrimitive.Trigger;
export const DrawerClose = DialogPrimitive.Close;

export function DrawerContent({
  className,
  children,
  side = 'right',
  width = 'md',
  showClose = true,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  side?: 'right' | 'left';
  width?: 'sm' | 'md' | 'lg';
  showClose?: boolean;
}) {
  const widthClass = { sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-lg' }[width];
  const sideClass =
    side === 'right'
      ? 'right-0 data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right'
      : 'left-0 data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left';

  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-overlay backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
      <DialogPrimitive.Content
        className={cn(
          'fixed inset-y-0 z-50 flex h-full w-full flex-col border-hairline bg-surface shadow-e3',
          side === 'right' ? 'border-l' : 'border-r',
          widthClass,
          sideClass,
          'duration-panel data-[state=open]:animate-in data-[state=closed]:animate-out',
          className,
        )}
        {...props}
      >
        {showClose && (
          <DialogPrimitive.Close
            className="absolute right-4 top-4 z-10 flex h-8 w-8 items-center justify-center rounded-sm text-text-muted transition-colors hover:bg-surface-sunken hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            aria-label="Close"
          >
            <X size={16} className="shrink-0" />
          </DialogPrimitive.Close>
        )}
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DrawerHeader({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('shrink-0 border-b border-hairline p-6 pb-4', className)}>{children}</div>
  );
}

export function DrawerTitle({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title className={cn('pr-8 text-h2 text-ink', className)} {...props}>
      {children}
    </DialogPrimitive.Title>
  );
}

export function DrawerDescription({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      className={cn('mt-1 text-body-sm text-text-muted', className)}
      {...props}
    >
      {children}
    </DialogPrimitive.Description>
  );
}

export function DrawerBody({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex-1 overflow-y-auto p-6', className)}>{children}</div>;
}

export function DrawerFooter({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'shrink-0 flex items-center justify-end gap-3 border-t border-hairline p-6',
        className,
      )}
    >
      {children}
    </div>
  );
}
